"""FastAPI application — main entry point for the autonomous trading dashboard."""

from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from ..database.connection import init_db, get_db
from .auth import (
    authenticate, create_session_cookie, get_current_user,
    COOKIE_NAME, COOKIE_MAX_AGE,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("quant_team")
logger.setLevel(logging.DEBUG)

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Scheduler reference
_scheduler = None

# Per-team session locks — prevents overlapping analysis runs
_session_locks: dict[str, bool] = {}


def _should_run_analysis(team_id: str) -> bool:
    """Decide whether to run analysis based on position urgency and time since last session."""
    from ..database.models import AgentSession, PortfolioPosition

    # Skip if session already in progress for this team
    if _session_locks.get(team_id, False):
        return False

    db = get_db()
    try:
        # Check time since last completed session
        last_session = (
            db.query(AgentSession)
            .filter_by(team_id=team_id)
            .order_by(AgentSession.created_at.desc())
            .first()
        )

        now = datetime.utcnow()
        minutes_since_last = float("inf")
        if last_session and last_session.created_at:
            minutes_since_last = (now - last_session.created_at).total_seconds() / 60

        # Always run first scan of the day (no session today)
        if last_session is None or (now - last_session.created_at) > timedelta(hours=12):
            logger.info(f"[{team_id}] First scan of the day — running analysis")
            return True

        # Check open positions for urgency
        positions = (
            db.query(PortfolioPosition)
            .filter_by(team_id=team_id, status="open")
            .all()
        )

        high_urgency = False
        for pos in positions:
            # Options near expiry (within 3 days)
            if pos.position_type in ("call", "put", "call_spread", "put_spread"):
                if pos.expiry and (pos.expiry - now.date()).days <= 3:
                    high_urgency = True
                    break

            # Large price move (>3% from entry)
            if pos.entry_price and pos.current_price:
                move_pct = abs(pos.current_price - pos.entry_price) / pos.entry_price * 100
                if move_pct > 3.0:
                    high_urgency = True
                    break

        # HIGH urgency: run every 10 minutes
        if high_urgency and minutes_since_last >= 10:
            logger.info(f"[{team_id}] HIGH urgency (options near expiry or large move) — running analysis")
            return True

        # NORMAL: run every 30 minutes
        if minutes_since_last >= 30:
            logger.info(f"[{team_id}] Normal schedule (30 min interval) — running analysis")
            return True

        return False
    except Exception as e:
        logger.error(f"[{team_id}] Error checking analysis urgency: {e}")
        return minutes_since_last >= 30  # Fall back to 30-min interval on error
    finally:
        db.close()


def _adaptive_tick():
    """Fires every 10 min during market hours. Decides per-team whether to run analysis."""
    try:
        from ..teams.registry import TeamRegistry
        registry = TeamRegistry()
        now = datetime.now()

        for config in registry.all():
            if _should_run_analysis(config.team_id):
                # Evolve strategy at end of day (after 3:25 PM)
                evolve = now.hour == 15 and now.minute >= 25
                _run_scheduled_session(team_id=config.team_id, evolve=evolve)
    except Exception as e:
        logger.error(f"Adaptive tick error: {e}")


def _setup_scheduler():
    """Configure APScheduler for autonomous operation with adaptive frequency."""
    global _scheduler

    schedule_enabled = os.environ.get("SCHEDULE_ENABLED", "").lower()
    # Default to true in production (when DATABASE_URL is set)
    if not schedule_enabled:
        schedule_enabled = "true" if os.environ.get("DATABASE_URL") else "false"

    if schedule_enabled != "true":
        logger.info("Scheduler disabled (SCHEDULE_ENABLED != true)")
        return

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    _scheduler = BackgroundScheduler(timezone="US/Eastern")

    # Adaptive analysis tick — fires every 10 min, decides per-team whether to run
    _scheduler.add_job(
        _adaptive_tick,
        CronTrigger(minute="*/10", hour="9-15", day_of_week="mon-fri"),
        id="adaptive_tick",
    )

    # Stop-loss checks every 5 minutes during market hours
    _scheduler.add_job(
        _run_stop_check,
        CronTrigger(minute="*/5", hour="9-15", day_of_week="mon-fri"),
        id="stop_check",
    )

    # Portfolio snapshots every 30 minutes
    _scheduler.add_job(
        _run_snapshot,
        CronTrigger(minute="0,30", hour="9-15", day_of_week="mon-fri"),
        id="snapshot",
    )

    _scheduler.start()
    logger.info("Scheduler started with adaptive frequency (10-min tick, 30-min normal, 10-min urgent)")


def _run_scheduled_session(team_id: str = "quant", evolve: bool = False):
    """Run an autonomous trading session."""
    # Per-team lock to prevent overlapping sessions
    if _session_locks.get(team_id, False):
        logger.warning(f"[{team_id}] Session already in progress, skipping")
        return

    _session_locks[team_id] = True
    try:
        import asyncio
        from ..orchestrator import TeamOrchestrator
        from ..teams.registry import TeamRegistry
        registry = TeamRegistry()
        config = registry.get(team_id)
        db = get_db()
        try:
            desk = TeamOrchestrator(config=config, db=db)
            asyncio.run(desk.run_trading_session(evolve_strategy=evolve))
            logger.info(f"Scheduled session for {team_id} completed")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Scheduled session error for {team_id}: {e}")
    finally:
        _session_locks[team_id] = False


def _run_stop_check():
    """Check stop-loss/take-profit on open positions."""
    try:
        from ..market.router import MarketDataRouter
        from ..trading.portfolio_manager import PortfolioManager
        from ..teams.registry import TeamRegistry, TeamConfig
        registry = TeamRegistry()
        for config in registry.all():
            db = get_db()
            try:
                market = MarketDataRouter(config)
                pm = PortfolioManager(db, market)
                closed = pm.check_stops(team_id=config.team_id)
                if closed:
                    logger.info(f"[{config.team_id}] Stop check closed {len(closed)} positions")
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Stop check error: {e}")


def _run_snapshot():
    """Take a portfolio snapshot."""
    try:
        from ..market.router import MarketDataRouter
        from ..trading.portfolio_manager import PortfolioManager
        from ..teams.registry import TeamRegistry
        registry = TeamRegistry()
        for config in registry.all():
            db = get_db()
            try:
                market = MarketDataRouter(config)
                pm = PortfolioManager(db, market)
                pm.take_snapshot(team_id=config.team_id)
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Snapshot error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _setup_scheduler()
    yield
    if _scheduler:
        _scheduler.shutdown()


app = FastAPI(
    title="Quant Team Dashboard",
    description="AI-powered autonomous stock trading desk",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# API routers
from .routers.recommendations import router as rec_router
from .routers.portfolio import router as portfolio_router
from .routers.market import router as market_router
from .routers.sessions import router as sessions_router
from .routers import teams

app.include_router(rec_router)
app.include_router(portfolio_router)
app.include_router(market_router)
app.include_router(sessions_router)
app.include_router(teams.router, prefix="/api/teams", tags=["teams"])


# ── Health ─────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check for Railway / load balancers."""
    return {
        "status": "ok",
        "scheduler_running": _scheduler is not None and _scheduler.running,
    }


# ── Auth helper ─────────────────────────────────────────────────

def _auth_required(request: Request):
    """Check if auth is configured and user is logged in."""
    # If no ALLOWED_USERS set, skip auth
    if not os.environ.get("ALLOWED_USERS"):
        return True
    return get_current_user(request) is not None


# ── Auth Pages ──────────────────────────────────────────────────

@app.get("/login")
async def login_page(request: Request):
    if _auth_required(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    if authenticate(email, password):
        response = RedirectResponse("/", status_code=302)
        cookie = create_session_cookie(email)
        response.set_cookie(COOKIE_NAME, cookie, max_age=COOKIE_MAX_AGE, httponly=True)
        return response
    return templates.TemplateResponse(request, "login.html", {"error": "Invalid credentials"})


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


# ── Page Routes ─────────────────────────────────────────────────

@app.get("/")
async def dashboard_page(request: Request):
    if not _auth_required(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/trades")
async def trades_page(request: Request):
    if not _auth_required(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "trades.html")


@app.get("/portfolio")
async def portfolio_page(request: Request):
    if not _auth_required(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "portfolio.html")


@app.get("/analysis")
async def analysis_page(request: Request):
    if not _auth_required(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "analysis.html")


@app.get("/market")
async def market_page(request: Request):
    if not _auth_required(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "market.html")


@app.get("/summary")
async def summary_page(request: Request):
    if not _auth_required(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "summary.html")


@app.get("/team/{team_id}")
async def team_detail_page(request: Request, team_id: str):
    if not _auth_required(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "team_detail.html", {"team_id": team_id})

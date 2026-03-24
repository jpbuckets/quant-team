"""FastAPI application — main entry point for the autonomous trading dashboard."""

from __future__ import annotations

import os
import logging
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


def _setup_scheduler():
    """Configure APScheduler for autonomous operation."""
    global _scheduler
    if os.environ.get("SCHEDULE_ENABLED", "").lower() != "true":
        logger.info("Scheduler disabled (SCHEDULE_ENABLED != true)")
        return

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    _scheduler = BackgroundScheduler(timezone="US/Eastern")

    # Trading sessions: 9:35 AM, 12:00 PM, 3:30 PM ET (weekdays)
    for hour, minute in [(9, 35), (12, 0), (15, 30)]:
        _scheduler.add_job(
            _run_scheduled_session,
            CronTrigger(hour=hour, minute=minute, day_of_week="mon-fri"),
            id=f"trade_{hour}_{minute}",
            kwargs={"evolve": hour == 15},  # Evolve strategy on last session
        )

    # Stop-loss checks every 5 minutes during market hours
    _scheduler.add_job(
        _run_stop_check,
        CronTrigger(minute="*/5", hour="9-15", day_of_week="mon-fri"),
        id="stop_check",
    )

    # Portfolio snapshots every 30 minutes during market hours
    _scheduler.add_job(
        _run_snapshot,
        CronTrigger(minute="0,30", hour="9-15", day_of_week="mon-fri"),
        id="snapshot",
    )

    _scheduler.start()
    logger.info("Scheduler started: trading sessions, stop checks, snapshots")


def _run_scheduled_session(evolve: bool = False):
    """Run an autonomous trading session."""
    try:
        from ..orchestrator import TradingDesk
        db = get_db()
        try:
            desk = TradingDesk(db=db)
            desk.run_trading_session(evolve_strategy=evolve)
            logger.info("Scheduled trading session completed")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Scheduled session error: {e}")


def _run_stop_check():
    """Check stop-loss/take-profit on open positions."""
    try:
        from ..market.stock_data import StockMarketData
        from ..trading.portfolio_manager import PortfolioManager
        db = get_db()
        try:
            market = StockMarketData()
            pm = PortfolioManager(db, market)
            closed = pm.check_stops()
            if closed:
                logger.info(f"Stop check closed {len(closed)} positions")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Stop check error: {e}")


def _run_snapshot():
    """Take a portfolio snapshot."""
    try:
        from ..market.stock_data import StockMarketData
        from ..trading.portfolio_manager import PortfolioManager
        db = get_db()
        try:
            market = StockMarketData()
            pm = PortfolioManager(db, market)
            pm.take_snapshot()
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
    version="0.3.0",
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

app.include_router(rec_router)
app.include_router(portfolio_router)
app.include_router(market_router)
app.include_router(sessions_router)


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




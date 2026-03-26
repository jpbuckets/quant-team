"""Trade decision API endpoints (autonomous — no accept/reject)."""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException, BackgroundTasks

from ...database.connection import get_db
from ...database.models import Recommendation
from ...trading.pdt import PDTChecker
from ...orchestrator import TeamOrchestrator
from ...teams.registry import TeamRegistry
from ..schemas import GenerateRequest

logger = logging.getLogger("quant_team")

router = APIRouter(prefix="/api/recommendations", tags=["trades"])

_sessions: dict[str, dict] = {}


def _rec_to_dict(rec: Recommendation) -> dict:
    return {
        "id": rec.id,
        "session_id": rec.session_id,
        "created_at": rec.created_at.isoformat() if rec.created_at else "",
        "ticker": rec.ticker,
        "action": rec.action,
        "position_type": rec.position_type,
        "quantity": rec.quantity,
        "strike": rec.strike,
        "strike2": rec.strike2,
        "expiry": str(rec.expiry) if rec.expiry else None,
        "reasoning": rec.reasoning,
        "stop_loss": rec.stop_loss,
        "stop_loss_pct": rec.stop_loss_pct,
        "take_profit": rec.take_profit,
        "take_profit_pct": rec.take_profit_pct,
        "confidence": rec.confidence,
        "timeframe": rec.timeframe,
        "status": rec.status,
        "entry_price": rec.entry_price,
        "exit_price": rec.exit_price,
        "outcome_pnl": rec.outcome_pnl,
        "outcome_pct": rec.outcome_pct,
        "closed_at": rec.closed_at.isoformat() if rec.closed_at else None,
    }


@router.get("")
def list_trades(
    status: str | None = None,
    ticker: str | None = None,
    limit: int = 50,
    team_id: str | None = None,
):
    db = get_db()
    try:
        query = db.query(Recommendation).order_by(Recommendation.created_at.desc())
        if status:
            query = query.filter(Recommendation.status == status)
        if ticker:
            query = query.filter(Recommendation.ticker == ticker.upper())
        if team_id is not None:
            query = query.filter(Recommendation.team_id == team_id)
        recs = query.limit(limit).all()
        return [_rec_to_dict(r) for r in recs]
    finally:
        db.close()


@router.get("/performance")
def trade_performance(team_id: str | None = None):
    db = get_db()
    try:
        query = db.query(Recommendation).filter(Recommendation.outcome_pnl.isnot(None))
        if team_id is not None:
            query = query.filter(Recommendation.team_id == team_id)
        closed = query.all()
        if not closed:
            return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pnl": 0, "avg_pnl": 0}

        wins = sum(1 for r in closed if r.outcome_pnl > 0)
        losses = sum(1 for r in closed if r.outcome_pnl <= 0)
        total_pnl = sum(r.outcome_pnl for r in closed)
        avg_pnl = total_pnl / len(closed) if closed else 0

        return {
            "total": len(closed),
            "wins": wins,
            "losses": losses,
            "win_rate": wins / len(closed) * 100 if closed else 0,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
        }
    finally:
        db.close()


@router.get("/pdt-status")
def pdt_status():
    db = get_db()
    try:
        checker = PDTChecker(db)
        return checker.get_status()
    finally:
        db.close()


def _update_progress(session_id: str, step: str, step_num: int, total_steps: int) -> None:
    if session_id in _sessions:
        _sessions[session_id]["progress"] = {"step": step, "step_num": step_num, "total_steps": total_steps}
    logger.info(f"Progress [{step_num}/{total_steps}]: {step}")


async def _run_session(session_id: str, tickers: list[str] | None) -> None:
    _sessions[session_id] = {"generating": True, "error": None, "progress": {"step": "Starting...", "step_num": 0, "total_steps": 6}}
    try:
        db = get_db()
        try:
            registry = TeamRegistry()
            config = registry.get("quant")  # Default to quant team for now
            desk = TeamOrchestrator(config=config, db=db)
            await desk.run_trading_session(tickers, on_progress=lambda s, n, t: _update_progress(session_id, s, n, t))
            _sessions[session_id]["progress"] = {"step": "Complete", "step_num": 6, "total_steps": 6}
            logger.info("Trading session completed successfully")
        finally:
            db.close()
    except asyncio.TimeoutError:
        _sessions[session_id]["error"] = "Analysis timed out after 5 minutes"
    except Exception as e:
        _sessions[session_id]["error"] = str(e)
        logger.error(f"Trading session failed: {e}", exc_info=True)
    finally:
        _sessions[session_id]["generating"] = False


@router.get("/status")
def generation_status():
    # Return status of most recent session or default
    if not _sessions:
        return {"generating": False, "error": None, "progress": {"step": "", "step_num": 0, "total_steps": 6}}
    latest_id = list(_sessions.keys())[-1]
    s = _sessions[latest_id]
    return {"generating": s["generating"], "error": s["error"], "progress": s["progress"], "session_id": latest_id}


@router.post("/generate")
async def run_trading_session(body: GenerateRequest, background_tasks: BackgroundTasks):
    if any(s["generating"] for s in _sessions.values()):
        raise HTTPException(status_code=409, detail="Session already in progress")
    session_id = str(uuid.uuid4())
    background_tasks.add_task(_run_session, session_id, body.tickers)
    return {"status": "started", "session_id": session_id, "message": "Trading session started — decisions will auto-execute"}

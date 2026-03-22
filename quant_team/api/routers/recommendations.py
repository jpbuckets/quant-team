"""Trade decision API endpoints (autonomous — no accept/reject)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, BackgroundTasks

from ...database.connection import get_db
from ...database.models import Recommendation
from ...trading.pdt import PDTChecker
from ...orchestrator import TradingDesk
from ..schemas import GenerateRequest

router = APIRouter(prefix="/api/recommendations", tags=["trades"])

_generating = False


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
):
    db = get_db()
    try:
        query = db.query(Recommendation).order_by(Recommendation.created_at.desc())
        if status:
            query = query.filter(Recommendation.status == status)
        if ticker:
            query = query.filter(Recommendation.ticker == ticker.upper())
        recs = query.limit(limit).all()
        return [_rec_to_dict(r) for r in recs]
    finally:
        db.close()


@router.get("/performance")
def trade_performance():
    db = get_db()
    try:
        closed = (
            db.query(Recommendation)
            .filter(Recommendation.outcome_pnl.isnot(None))
            .all()
        )
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


def _run_session(tickers: list[str] | None):
    global _generating
    _generating = True
    try:
        db = get_db()
        try:
            desk = TradingDesk(db=db, tickers=tickers)
            desk.run_trading_session(tickers)
        finally:
            db.close()
    finally:
        _generating = False


@router.post("/generate")
def run_trading_session(
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
):
    global _generating
    if _generating:
        raise HTTPException(status_code=409, detail="Session already in progress")
    background_tasks.add_task(_run_session, body.tickers)
    return {"status": "started", "message": "Trading session started — decisions will auto-execute"}

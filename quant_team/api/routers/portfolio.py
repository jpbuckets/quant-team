"""Portfolio API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from ...database.connection import get_db
from ...database.models import PortfolioSnapshot, TradeRecord
from ...market.stock_data import StockMarketData
from ...trading.portfolio_manager import PortfolioManager

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("")
def get_portfolio(team_id: str = "quant"):
    db = get_db()
    try:
        market = StockMarketData()
        pm = PortfolioManager(db, market)
        return pm.get_current_value(team_id=team_id)
    finally:
        db.close()


@router.get("/history")
def get_portfolio_history(limit: int = 200, team_id: str = "quant"):
    db = get_db()
    try:
        snapshots = (
            db.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.team_id == team_id)
            .order_by(PortfolioSnapshot.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "timestamp": s.timestamp.isoformat() if s.timestamp else "",
                "total_value": s.total_value,
                "cash": s.cash,
                "total_return_pct": s.total_return_pct,
            }
            for s in reversed(snapshots)
        ]
    finally:
        db.close()


@router.get("/trades")
def get_trade_history(limit: int = 50, team_id: str = "quant"):
    db = get_db()
    try:
        trades = (
            db.query(TradeRecord)
            .filter(TradeRecord.team_id == team_id)
            .order_by(TradeRecord.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": t.id,
                "ticker": t.ticker,
                "action": t.action,
                "position_type": t.position_type,
                "price": t.price,
                "quantity": t.quantity,
                "notional": t.notional,
                "pnl": t.pnl,
                "reasoning": t.reasoning,
                "timestamp": t.timestamp.isoformat() if t.timestamp else "",
            }
            for t in trades
        ]
    finally:
        db.close()


@router.post("/positions/{position_id}/close")
def close_position(position_id: int, team_id: str = "quant"):
    db = get_db()
    try:
        market = StockMarketData()
        pm = PortfolioManager(db, market)
        trade = pm.close_position(position_id)
        if trade is None:
            raise HTTPException(status_code=400, detail="Cannot close position (not found or already closed)")
        return {
            "status": "closed",
            "pnl": trade.pnl,
            "price": trade.price,
        }
    finally:
        db.close()


@router.post("/reset")
def reset_portfolio(team_id: str = "quant"):
    db = get_db()
    try:
        market = StockMarketData()
        pm = PortfolioManager(db, market)
        pm.reset(team_id=team_id)
        return {"status": "reset", "cash": 10000.0}
    finally:
        db.close()


@router.post("/snapshot")
def take_snapshot(team_id: str = "quant"):
    db = get_db()
    try:
        market = StockMarketData()
        pm = PortfolioManager(db, market)
        snapshot = pm.take_snapshot(team_id=team_id)
        return {"status": "ok", "total_value": snapshot.total_value}
    finally:
        db.close()

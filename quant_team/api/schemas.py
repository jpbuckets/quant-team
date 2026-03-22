"""Pydantic schemas for API request/response models."""

from __future__ import annotations

from datetime import datetime, date
from pydantic import BaseModel


class RecommendationOut(BaseModel):
    id: int
    session_id: int | None = None
    created_at: str
    ticker: str
    action: str
    position_type: str
    quantity: float | None = None
    strike: float | None = None
    strike2: float | None = None
    expiry: str | None = None
    reasoning: str
    stop_loss: float | None = None
    stop_loss_pct: float | None = None
    take_profit: float | None = None
    take_profit_pct: float | None = None
    confidence: str | None = None
    timeframe: str | None = None
    status: str
    entry_price: float | None = None
    exit_price: float | None = None
    outcome_pnl: float | None = None
    outcome_pct: float | None = None
    closed_at: str | None = None

    class Config:
        from_attributes = True


class PositionOut(BaseModel):
    id: int
    ticker: str
    position_type: str
    quantity: float
    entry_price: float
    current_price: float
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    pnl_pct: float
    strike: float | None = None
    expiry: str | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: str | None = None


class PortfolioOut(BaseModel):
    total_value: float
    cash: float
    invested: float
    unrealized_pnl: float
    realized_pnl: float
    total_return_pct: float
    drawdown_pct: float
    initial_capital: float
    positions: list[PositionOut]


class TradeOut(BaseModel):
    id: int
    ticker: str
    action: str
    position_type: str
    price: float
    quantity: float
    notional: float
    pnl: float
    reasoning: str | None = None
    timestamp: str

    class Config:
        from_attributes = True


class SessionOut(BaseModel):
    id: int
    timestamp: str
    tickers_analyzed: str | None = None
    macro_analysis: str | None = None
    quant_analysis: str | None = None
    risk_analysis: str | None = None
    cio_decision: str | None = None
    recommendations_count: int

    class Config:
        from_attributes = True


class SnapshotOut(BaseModel):
    timestamp: str
    total_value: float
    cash: float
    total_return_pct: float | None = None

    class Config:
        from_attributes = True


class QuoteOut(BaseModel):
    ticker: str
    price: float
    previous_close: float
    open: float
    day_high: float
    day_low: float
    volume: int
    market_cap: float
    change_pct: float


class GenerateRequest(BaseModel):
    tickers: list[str] | None = None

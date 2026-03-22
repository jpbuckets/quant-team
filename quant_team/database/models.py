"""SQLAlchemy ORM models for the recommendation dashboard."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column, Integer, Float, String, Text, DateTime, Date, Boolean,
    ForeignKey, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("agent_sessions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    ticker = Column(String(10), nullable=False)
    action = Column(String(10), nullable=False)  # BUY, SELL, HOLD
    position_type = Column(String(20), nullable=False)  # shares, call, put, call_spread, put_spread
    quantity = Column(Float, nullable=True)  # shares or contracts
    strike = Column(Float, nullable=True)
    strike2 = Column(Float, nullable=True)  # for spreads
    expiry = Column(Date, nullable=True)
    reasoning = Column(Text, nullable=False)
    stop_loss = Column(Float, nullable=True)
    stop_loss_pct = Column(Float, nullable=True)  # for options
    take_profit = Column(Float, nullable=True)
    take_profit_pct = Column(Float, nullable=True)  # for options
    confidence = Column(String(10), nullable=True)
    timeframe = Column(String(10), nullable=True)
    status = Column(String(20), default="pending")  # pending, accepted, rejected, expired

    # Performance tracking
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    outcome_pnl = Column(Float, nullable=True)
    outcome_pct = Column(Float, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    session = relationship("AgentSession", back_populates="recommendations")
    position = relationship("PortfolioPosition", back_populates="recommendation", uselist=False)


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=True)
    ticker = Column(String(10), nullable=False)
    position_type = Column(String(20), nullable=False)
    entry_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    strike = Column(Float, nullable=True)
    strike2 = Column(Float, nullable=True)
    expiry = Column(Date, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    exit_price = Column(Float, nullable=True)
    realized_pnl = Column(Float, default=0.0)
    status = Column(String(10), default="open")  # open, closed, expired

    recommendation = relationship("Recommendation", back_populates="position")
    trades = relationship("TradeRecord", back_populates="position")


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    total_value = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    invested = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=False)
    day_return_pct = Column(Float, nullable=True)
    total_return_pct = Column(Float, nullable=True)


class TradeRecord(Base):
    __tablename__ = "trade_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(Integer, ForeignKey("portfolio_positions.id"), nullable=True)
    recommendation_id = Column(Integer, ForeignKey("recommendations.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    ticker = Column(String(10), nullable=False)
    action = Column(String(10), nullable=False)
    position_type = Column(String(20), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    notional = Column(Float, nullable=False)
    pnl = Column(Float, default=0.0)
    reasoning = Column(Text, nullable=True)

    position = relationship("PortfolioPosition", back_populates="trades")


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    tickers_analyzed = Column(Text, nullable=True)  # JSON array
    market_context_summary = Column(Text, nullable=True)
    macro_analysis = Column(Text, nullable=True)
    quant_analysis = Column(Text, nullable=True)
    risk_analysis = Column(Text, nullable=True)
    cio_decision = Column(Text, nullable=True)
    recommendations_count = Column(Integer, default=0)

    recommendations = relationship("Recommendation", back_populates="session")


class PortfolioState(Base):
    __tablename__ = "portfolio_state"

    id = Column(Integer, primary_key=True)  # always 1
    cash = Column(Float, default=10000.0)
    initial_capital = Column(Float, default=10000.0)
    peak_value = Column(Float, default=10000.0)
    total_realized_pnl = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow)

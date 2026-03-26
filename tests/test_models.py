"""Tests for database model team_id scoping (TEAM-02)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from quant_team.database.models import (
    Base, Recommendation, PortfolioPosition, PortfolioSnapshot,
    TradeRecord, AgentSession, PortfolioState,
)
from quant_team.database.connection import _maybe_add_team_id


def test_team_id_on_agent_session(test_db):
    """AgentSession model has team_id column with default 'quant'."""
    session = AgentSession(tickers_analyzed="[]")
    test_db.add(session)
    test_db.commit()
    assert session.team_id == "quant"


def test_team_id_on_recommendation(test_db):
    """Recommendation model has team_id column with default 'quant'."""
    rec = Recommendation(ticker="AAPL", action="BUY", position_type="shares", reasoning="test")
    test_db.add(rec)
    test_db.commit()
    assert rec.team_id == "quant"


def test_team_id_on_portfolio_position(test_db):
    """PortfolioPosition model has team_id column with default 'quant'."""
    pos = PortfolioPosition(ticker="AAPL", position_type="shares", entry_price=150.0, quantity=10)
    test_db.add(pos)
    test_db.commit()
    assert pos.team_id == "quant"


def test_team_id_on_trade_record(test_db):
    """TradeRecord model has team_id column with default 'quant'."""
    trade = TradeRecord(ticker="AAPL", action="BUY", position_type="shares", price=150.0, quantity=10, notional=1500.0)
    test_db.add(trade)
    test_db.commit()
    assert trade.team_id == "quant"


def test_team_id_on_portfolio_state(test_db):
    """PortfolioState model has team_id column with default 'quant'."""
    # test_db fixture already creates a PortfolioState
    state = test_db.query(PortfolioState).first()
    assert state.team_id == "quant"


def test_team_id_on_portfolio_snapshot(test_db):
    """PortfolioSnapshot model has team_id column with default 'quant'."""
    snap = PortfolioSnapshot(total_value=10000.0, cash=10000.0, invested=0.0, unrealized_pnl=0.0, realized_pnl=0.0)
    test_db.add(snap)
    test_db.commit()
    assert snap.team_id == "quant"


def test_migration_adds_team_id_to_existing_db():
    """Migration function adds team_id column to existing tables without data loss."""
    # Create a DB with OLD schema (no team_id)
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE agent_sessions (id INTEGER PRIMARY KEY, timestamp TEXT)"))
        conn.execute(text("INSERT INTO agent_sessions (id, timestamp) VALUES (1, '2024-01-01')"))
        conn.commit()

    # Run migration
    _maybe_add_team_id(engine)

    # Verify column added with default
    inspector = inspect(engine)
    cols = [c["name"] for c in inspector.get_columns("agent_sessions")]
    assert "team_id" in cols

    # Verify existing data preserved with default
    with engine.connect() as conn:
        result = conn.execute(text("SELECT team_id FROM agent_sessions WHERE id = 1"))
        row = result.fetchone()
        assert row[0] == "quant"

    engine.dispose()

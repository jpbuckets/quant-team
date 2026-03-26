"""Tests for PaperExecutor — paper trade execution behavior."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from quant_team.database.models import (
    Base, PortfolioState, PortfolioPosition, TradeRecord, Recommendation,
)
from quant_team.trading.execution import ExecutionResult, BaseExecutor, PaperExecutor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db():
    """In-memory SQLite database with initialized portfolio state."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    state = PortfolioState(
        cash=10000.0, initial_capital=10000.0,
        peak_value=10000.0, total_realized_pnl=0.0,
        team_id="test",
    )
    db.add(state)
    db.commit()
    yield db
    db.close()
    engine.dispose()


@pytest.fixture
def mock_market():
    """Mock MarketDataRouter returning a fixed quote of $150.00."""
    market = MagicMock()
    market.fetch_quote.return_value = {"price": 150.0}
    return market


@pytest.fixture
def buy_rec(test_db):
    """A pending BUY recommendation for AAPL shares."""
    rec = Recommendation(
        team_id="test",
        ticker="AAPL",
        action="BUY",
        position_type="shares",
        quantity=10.0,
        reasoning="Strong momentum signal",
        status="pending",
    )
    test_db.add(rec)
    test_db.commit()
    return rec


@pytest.fixture
def sell_rec(test_db):
    """A pending SELL recommendation for AAPL shares."""
    rec = Recommendation(
        team_id="test",
        ticker="AAPL",
        action="SELL",
        position_type="shares",
        quantity=10.0,
        reasoning="Take profit signal",
        status="pending",
    )
    test_db.add(rec)
    test_db.commit()
    return rec


@pytest.fixture
def open_position(test_db):
    """An existing open position for AAPL shares (10 @ $140.00)."""
    pos = PortfolioPosition(
        team_id="test",
        ticker="AAPL",
        position_type="shares",
        entry_price=140.0,
        quantity=10.0,
        status="open",
    )
    test_db.add(pos)
    test_db.commit()
    return pos


# ---------------------------------------------------------------------------
# Test 1: Successful BUY
# ---------------------------------------------------------------------------

def test_paper_executor_buy_success(test_db, mock_market, buy_rec):
    """execute_buy() opens a position, deducts cash, writes a TradeRecord, returns success."""
    executor = PaperExecutor()
    result = executor.execute_buy(buy_rec, mock_market, test_db, team_id="test")

    assert result.success is True, f"Expected success, got: {result.reason}"

    # Position created
    pos = test_db.query(PortfolioPosition).filter_by(ticker="AAPL", status="open").first()
    assert pos is not None
    assert pos.status == "open"
    assert pos.team_id == "test"

    # Cash deducted (10 shares @ $150 = $1500)
    state = test_db.query(PortfolioState).filter_by(team_id="test").first()
    assert state.cash == pytest.approx(10000.0 - 150.0 * 10.0)

    # TradeRecord written
    trade = test_db.query(TradeRecord).filter_by(ticker="AAPL", action="BUY").first()
    assert trade is not None

    # ExecutionResult fields populated
    assert result.trade_record is not None
    assert result.position is not None
    assert result.simulated_price == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# Test 2: BUY with insufficient cash
# ---------------------------------------------------------------------------

def test_paper_executor_buy_insufficient_cash(test_db, mock_market):
    """execute_buy() with cost exceeding cash returns failure."""
    # Drain cash to $100
    state = test_db.query(PortfolioState).filter_by(team_id="test").first()
    state.cash = 100.0
    test_db.commit()

    rec = Recommendation(
        team_id="test",
        ticker="AAPL",
        action="BUY",
        position_type="shares",
        quantity=10.0,  # cost = 150 * 10 = 1500 > 100
        reasoning="Buy signal",
        status="pending",
    )
    test_db.add(rec)
    test_db.commit()

    executor = PaperExecutor()
    result = executor.execute_buy(rec, mock_market, test_db, team_id="test")

    assert result.success is False
    assert "insufficient cash" in result.reason.lower()

    # No position created
    pos = test_db.query(PortfolioPosition).filter_by(ticker="AAPL", status="open").first()
    assert pos is None


# ---------------------------------------------------------------------------
# Test 3: Successful SELL
# ---------------------------------------------------------------------------

def test_paper_executor_sell_success(test_db, mock_market, sell_rec, open_position):
    """execute_sell() closes open position, adds proceeds to cash, writes SELL TradeRecord."""
    initial_state = test_db.query(PortfolioState).filter_by(team_id="test").first()
    cash_before = initial_state.cash

    executor = PaperExecutor()
    result = executor.execute_sell(sell_rec, mock_market, test_db, team_id="test")

    assert result.success is True, f"Expected success, got: {result.reason}"

    # Position closed
    pos = test_db.query(PortfolioPosition).get(open_position.id)
    assert pos.status == "closed"

    # Cash increased by proceeds (10 shares @ $150 = $1500)
    state = test_db.query(PortfolioState).filter_by(team_id="test").first()
    assert state.cash == pytest.approx(cash_before + 150.0 * 10.0)

    # TradeRecord with action=SELL
    trade = test_db.query(TradeRecord).filter_by(ticker="AAPL", action="SELL").first()
    assert trade is not None

    # ExecutionResult populated
    assert result.trade_record is not None
    assert result.position is not None
    assert result.simulated_price == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# Test 4: SELL with no open position
# ---------------------------------------------------------------------------

def test_paper_executor_sell_no_open_position(test_db, mock_market, sell_rec):
    """execute_sell() when no open position exists returns failure with 'No open position'."""
    executor = PaperExecutor()
    result = executor.execute_sell(sell_rec, mock_market, test_db, team_id="test")

    assert result.success is False
    assert "no open position" in result.reason.lower()


# ---------------------------------------------------------------------------
# Test 5: ExecutionResult dataclass fields
# ---------------------------------------------------------------------------

def test_execution_result_fields():
    """ExecutionResult has correct fields with right types and defaults."""
    result = ExecutionResult(success=True)
    assert result.success is True
    assert result.trade_record is None
    assert result.position is None
    assert result.reason == ""
    assert result.simulated_price == 0.0

    result2 = ExecutionResult(
        success=False,
        trade_record=None,
        position=None,
        reason="Insufficient cash",
        simulated_price=150.0,
    )
    assert result2.success is False
    assert result2.reason == "Insufficient cash"
    assert result2.simulated_price == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# Test 6: TradeRecord.reasoning has [PAPER] prefix
# ---------------------------------------------------------------------------

def test_paper_executor_trade_record_has_paper_prefix(test_db, mock_market, buy_rec):
    """TradeRecord.reasoning written by PaperExecutor starts with '[PAPER]'."""
    executor = PaperExecutor()
    result = executor.execute_buy(buy_rec, mock_market, test_db, team_id="test")

    assert result.success is True
    trade = test_db.query(TradeRecord).filter_by(ticker="AAPL", action="BUY").first()
    assert trade is not None
    assert trade.reasoning.startswith("[PAPER]")

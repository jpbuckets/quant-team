"""Shared test fixtures for Phase 1."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from quant_team.database.models import Base, PortfolioState


@pytest.fixture
def test_db():
    """In-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    # Initialize portfolio state
    state = PortfolioState(id=1, cash=10000.0, initial_capital=10000.0, peak_value=10000.0, total_realized_pnl=0.0)
    db.add(state)
    db.commit()
    yield db
    db.close()
    engine.dispose()


@pytest.fixture
def test_engine():
    """In-memory SQLite engine for migration tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response object."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Mock agent analysis response")]
    return mock_response


@pytest.fixture
def mock_async_anthropic(mock_anthropic_response):
    """Mock AsyncAnthropic client that returns canned responses."""
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
    return mock_client


@pytest.fixture
def sample_team_config_dict():
    """Sample team config as a dict (as loaded from YAML)."""
    return {
        "team_id": "test-team",
        "name": "Test Team",
        "asset_class": "stocks",
        "execution_backend": "paper",
        "watchlist": ["AAPL", "MSFT"],
        "risk_limits": {
            "max_position_pct": 20.0,
            "max_exposure_pct": 80.0,
            "max_drawdown_pct": 20.0,
            "max_options_pct": 30.0,
        },
        "schedule_cron": [{"hour": 9, "minute": 35}],
        "agents": [
            {
                "name": "TestAgent",
                "title": "Test Analyst",
                "system_prompt": "You are a test agent.",
                "model": "claude-sonnet-4-20250514",
            }
        ],
    }

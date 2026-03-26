"""Tests for ExecutionRouter and Teams API endpoints."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from quant_team.trading.execution_router import ExecutionRouter
from quant_team.trading.execution import PaperExecutor
from quant_team.teams.registry import TeamConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def stock_config():
    """TeamConfig for a stock team with paper execution backend."""
    return TeamConfig(
        team_id="quant",
        name="Quant Stocks Team",
        asset_class="stocks",
        execution_backend="paper",
    )


@pytest.fixture
def router(stock_config):
    """ExecutionRouter for a paper stock team."""
    return ExecutionRouter(stock_config)


# ---------------------------------------------------------------------------
# Test 1: ExecutionRouter with paper backend creates PaperExecutor
# ---------------------------------------------------------------------------

def test_execution_router_paper_creates_paper_executor(stock_config):
    """ExecutionRouter with execution_backend='paper' wraps PaperExecutor."""
    er = ExecutionRouter(stock_config)
    assert isinstance(er._executor, PaperExecutor)


# ---------------------------------------------------------------------------
# Test 2: update_backend hot-swaps the executor
# ---------------------------------------------------------------------------

def test_execution_router_update_backend_hot_swaps(router):
    """update_backend('paper') replaces the internal executor instance."""
    old_executor = router._executor
    router.update_backend("paper")
    # A new PaperExecutor instance should have been created
    assert isinstance(router._executor, PaperExecutor)
    assert router._executor is not old_executor


# ---------------------------------------------------------------------------
# Test 3: Unknown backend raises ValueError
# ---------------------------------------------------------------------------

def test_execution_router_unknown_backend_raises(stock_config):
    """ExecutionRouter raises ValueError for unrecognized backends."""
    stock_config.execution_backend = "alpaca"
    with pytest.raises(ValueError, match="Unknown execution_backend"):
        ExecutionRouter(stock_config)


def test_execution_router_update_backend_unknown_raises(router):
    """update_backend raises ValueError for unrecognized backends."""
    with pytest.raises(ValueError, match="Unknown execution_backend"):
        router.update_backend("solana")


# ---------------------------------------------------------------------------
# Teams API tests — setup client
# ---------------------------------------------------------------------------

@pytest.fixture
def teams_client():
    """TestClient for the FastAPI app, with TeamRegistry mocked."""
    from quant_team.api.app import app
    from quant_team.teams.registry import TeamConfig

    mock_configs = [
        TeamConfig(
            team_id="quant",
            name="Quant Stocks Team",
            asset_class="stocks",
            execution_backend="paper",
            watchlist=["AAPL", "MSFT"],
        ),
        TeamConfig(
            team_id="crypto",
            name="Crypto DeFi Team",
            asset_class="crypto",
            execution_backend="paper",
            watchlist=["SOL"],
        ),
    ]

    def mock_all():
        return mock_configs

    def mock_get(team_id: str):
        mapping = {c.team_id: c for c in mock_configs}
        if team_id not in mapping:
            raise KeyError(f"Unknown team: {team_id}")
        return mapping[team_id]

    with patch("quant_team.api.routers.teams.TeamRegistry") as MockRegistry:
        instance = MagicMock()
        instance.all.side_effect = mock_all
        instance.get.side_effect = mock_get
        MockRegistry.return_value = instance
        client = TestClient(app)
        yield client


# ---------------------------------------------------------------------------
# Test 4: GET /api/teams returns list with execution_backend
# ---------------------------------------------------------------------------

def test_teams_list_returns_all_with_execution_backend(teams_client):
    """GET /api/teams returns all teams including execution_backend field."""
    response = teams_client.get("/api/teams")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    team_ids = {t["team_id"] for t in data}
    assert "quant" in team_ids
    assert "crypto" in team_ids
    for team in data:
        assert "execution_backend" in team
        assert team["execution_backend"] == "paper"


# ---------------------------------------------------------------------------
# Test 5: PATCH /api/teams/{team_id}/execution-mode updates mode
# ---------------------------------------------------------------------------

def test_teams_toggle_execution_mode_success(teams_client):
    """PATCH /api/teams/{team_id}/execution-mode returns 200 with updated backend."""
    response = teams_client.patch(
        "/api/teams/quant/execution-mode",
        json={"mode": "paper"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["team_id"] == "quant"
    assert data["execution_backend"] == "paper"


# ---------------------------------------------------------------------------
# Test 6: PATCH /api/teams/{team_id}/execution-mode with invalid team_id → 404
# ---------------------------------------------------------------------------

def test_teams_toggle_invalid_team_returns_404(teams_client):
    """PATCH /api/teams/unknown/execution-mode returns 404 for unknown team."""
    response = teams_client.patch(
        "/api/teams/unknown-team/execution-mode",
        json={"mode": "paper"},
    )
    assert response.status_code == 404

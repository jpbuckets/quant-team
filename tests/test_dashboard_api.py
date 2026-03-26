"""Dashboard API contract tests for team-scoped endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from quant_team.api.app import app

client = TestClient(app)


# ── Task 1: team_id filtering on portfolio/recommendations/sessions ───────────


def test_portfolio_with_team_id():
    """GET /api/portfolio?team_id=quant returns 200."""
    response = client.get("/api/portfolio?team_id=quant")
    assert response.status_code == 200
    data = response.json()
    assert "total_value" in data
    assert "cash" in data
    assert "positions" in data


def test_portfolio_default_backward_compat():
    """GET /api/portfolio (no team_id) defaults to quant team — backward compat."""
    response = client.get("/api/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert "total_value" in data
    assert "cash" in data


def test_recommendations_with_team_id():
    """GET /api/recommendations?team_id=quant filters by team_id."""
    response = client.get("/api/recommendations?team_id=quant")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_sessions_with_team_id():
    """GET /api/sessions?team_id=quant filters by team_id."""
    response = client.get("/api/sessions?team_id=quant")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_trade_history_with_team_id():
    """GET /api/portfolio/trades?team_id=quant filters trade records by team_id."""
    response = client.get("/api/portfolio/trades?team_id=quant")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_portfolio_history_with_team_id():
    """GET /api/portfolio/history?team_id=quant filters snapshots by team_id."""
    response = client.get("/api/portfolio/history?team_id=quant")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ── Task 2: cross-team summary and team detail endpoints ─────────────────────


def test_teams_summary():
    """GET /api/teams/summary returns 200 with aggregate and teams keys."""
    response = client.get("/api/teams/summary")
    assert response.status_code == 200
    data = response.json()
    assert "aggregate" in data
    assert "teams" in data
    aggregate = data["aggregate"]
    assert "total_value" in aggregate
    assert "cash" in aggregate


def test_team_detail():
    """GET /api/teams/quant returns 200 with team detail including execution_backend."""
    response = client.get("/api/teams/quant")
    assert response.status_code == 200
    data = response.json()
    assert data["team_id"] == "quant"
    assert "execution_backend" in data
    assert "name" in data
    assert "asset_class" in data


def test_team_detail_not_found():
    """GET /api/teams/nonexistent returns 404."""
    response = client.get("/api/teams/nonexistent")
    assert response.status_code == 404


def test_teams_list_has_execution_backend():
    """GET /api/teams returns list with execution_backend field on each entry."""
    response = client.get("/api/teams")
    assert response.status_code == 200
    teams = response.json()
    assert isinstance(teams, list)
    for team in teams:
        assert "execution_backend" in team
        assert "team_id" in team

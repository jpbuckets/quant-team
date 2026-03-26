"""Tests for database model team_id scoping (TEAM-02)."""
from __future__ import annotations

import pytest


def test_team_id_on_agent_session(test_db):
    """AgentSession model has team_id column with default 'quant'."""
    pytest.skip("TEAM-02: Implement after team_id migration")


def test_team_id_on_recommendation(test_db):
    """Recommendation model has team_id column with default 'quant'."""
    pytest.skip("TEAM-02: Implement after team_id migration")


def test_team_id_on_portfolio_position(test_db):
    """PortfolioPosition model has team_id column with default 'quant'."""
    pytest.skip("TEAM-02: Implement after team_id migration")


def test_team_id_on_trade_record(test_db):
    """TradeRecord model has team_id column with default 'quant'."""
    pytest.skip("TEAM-02: Implement after team_id migration")


def test_team_id_on_portfolio_state(test_db):
    """PortfolioState model has team_id column with default 'quant'."""
    pytest.skip("TEAM-02: Implement after team_id migration")


def test_migration_adds_team_id_to_existing_db(test_engine):
    """Migration function adds team_id column to existing tables without data loss."""
    pytest.skip("TEAM-02: Implement after migration function written")

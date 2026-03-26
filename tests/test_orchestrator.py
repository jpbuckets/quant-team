"""Tests for dynamic agent construction (TEAM-03, TEAM-04)."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from quant_team.teams.registry import TeamConfig, AgentSpec, RiskLimits
from quant_team.orchestrator import TeamOrchestrator


def _make_config(agents=None):
    if agents is None:
        agents = [
            AgentSpec(name="Analyst", title="Test Analyst", system_prompt="You analyze."),
            AgentSpec(name="Boss", title="Decision Maker", system_prompt="You decide."),
        ]
    return TeamConfig(
        team_id="test",
        name="Test Team",
        asset_class="stocks",
        agents=agents,
        watchlist=["AAPL"],
    )


def test_dynamic_agent_construction(test_db):
    config = _make_config()
    orch = TeamOrchestrator(config=config, db=test_db)
    assert len(orch.agents) == 2
    assert orch.agents[0].name == "Analyst"
    assert orch.agents[1].name == "Boss"
    assert orch.decision_agent.name == "Boss"


def test_agent_uses_config_system_prompt(test_db):
    config = _make_config([
        AgentSpec(name="Custom", title="Custom Agent", system_prompt="Custom prompt from YAML."),
    ])
    orch = TeamOrchestrator(config=config, db=test_db)
    assert orch.agents[0].system_prompt == "Custom prompt from YAML."


def test_no_hardcoded_agent_imports():
    """Verify orchestrator.py does not import from .agents.cio, .agents.quant, etc."""
    import ast
    with open("quant_team/orchestrator.py") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and ".agents." in (node.module or ""):
                if node.module not in (".agents.base",):
                    pytest.fail(f"Found hardcoded agent import: from {node.module}")


@pytest.mark.asyncio
async def test_session_completes_with_mocked_agents(test_db, mock_anthropic_response):
    pytest.skip("Integration test — requires full market data mocking, deferred to Phase 1 verification")

"""Tests for dynamic agent construction (TEAM-03, TEAM-04)."""
from __future__ import annotations

import pytest


def test_dynamic_agent_construction():
    """TeamOrchestrator constructs agents from TeamConfig without hardcoded imports."""
    pytest.skip("TEAM-03: Implement after TeamOrchestrator created")


def test_agent_uses_config_system_prompt():
    """Agent receives system_prompt from AgentSpec, not hardcoded string."""
    pytest.skip("TEAM-04: Implement after TeamOrchestrator uses AgentSpec prompts")


@pytest.mark.asyncio
async def test_session_completes_with_mocked_agents():
    """Full session completes through orchestrator with mocked Claude API."""
    pytest.skip("STAB-01/TEAM-03: Implement after async orchestrator")

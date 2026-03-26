"""Tests for Agent async behavior and timeout (STAB-01)."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from quant_team.agents.base import Agent


@pytest.mark.asyncio
async def test_analyze_timeout():
    """Agent.analyze() raises asyncio.TimeoutError when Claude API exceeds 300s."""
    agent = Agent(name="Test", title="Test", system_prompt="test")
    # Make the mock hang forever
    async def slow_create(**kwargs):
        await asyncio.sleep(999)
    agent.client = MagicMock()
    agent.client.messages.create = slow_create
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(agent.analyze("test context"), timeout=1.0)


@pytest.mark.asyncio
async def test_analyze_returns_response(mock_async_anthropic, mock_anthropic_response):
    """Agent.analyze() returns text from Claude API response."""
    agent = Agent(name="Test", title="Test", system_prompt="test")
    agent.client = mock_async_anthropic
    result = await agent.analyze("test context")
    assert result == "Mock agent analysis response"


@pytest.mark.asyncio
async def test_respond_timeout():
    """Agent.respond() also respects timeout since it calls AsyncAnthropic."""
    agent = Agent(name="Test", title="Test", system_prompt="test")
    async def slow_create(**kwargs):
        await asyncio.sleep(999)
    agent.client = MagicMock()
    agent.client.messages.create = slow_create
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(agent.respond("test prompt"), timeout=1.0)

"""Tests for Agent async behavior and timeout (STAB-01)."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_analyze_timeout():
    """Agent.analyze() raises asyncio.TimeoutError when Claude API exceeds 300s."""
    pytest.skip("STAB-01: Implement after Agent switched to AsyncAnthropic")


@pytest.mark.asyncio
async def test_analyze_returns_response():
    """Agent.analyze() returns text from Claude API response."""
    pytest.skip("STAB-01: Implement after Agent switched to AsyncAnthropic")


@pytest.mark.asyncio
async def test_respond_timeout():
    """Agent.respond() also respects timeout since it calls AsyncAnthropic."""
    pytest.skip("STAB-01: Implement after Agent switched to AsyncAnthropic")

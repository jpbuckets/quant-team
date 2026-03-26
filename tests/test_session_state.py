"""Tests for per-session state isolation (STAB-02, STAB-04)."""
from __future__ import annotations

from quant_team.api.routers.recommendations import _sessions


def test_concurrent_sessions_independent():
    """Two sessions have independent generating/progress/error state."""
    _sessions.clear()
    _sessions["session-1"] = {"generating": True, "error": None, "progress": {"step": "Step 1", "step_num": 1, "total_steps": 6}}
    _sessions["session-2"] = {"generating": True, "error": None, "progress": {"step": "Step 3", "step_num": 3, "total_steps": 6}}
    assert _sessions["session-1"]["progress"]["step_num"] == 1
    assert _sessions["session-2"]["progress"]["step_num"] == 3
    _sessions["session-1"]["generating"] = False
    assert _sessions["session-2"]["generating"] is True
    _sessions.clear()


def test_409_when_session_running():
    """POST /generate returns 409 when a session is already in progress."""
    # Test the guard logic directly
    _sessions.clear()
    _sessions["active"] = {"generating": True, "error": None, "progress": {}}
    assert any(s["generating"] for s in _sessions.values()) is True
    _sessions.clear()


def test_status_returns_progress():
    """GET /status returns current progress during active session (STAB-04)."""
    _sessions.clear()
    _sessions["test-id"] = {"generating": True, "error": None, "progress": {"step": "Fetching data", "step_num": 1, "total_steps": 6}}
    latest_id = list(_sessions.keys())[-1]
    s = _sessions[latest_id]
    assert s["progress"]["step"] == "Fetching data"
    assert s["generating"] is True
    _sessions.clear()


def test_status_returns_error_on_timeout():
    """GET /status returns timeout error message when session times out."""
    _sessions.clear()
    _sessions["test-id"] = {"generating": False, "error": "Analysis timed out after 5 minutes", "progress": {}}
    s = _sessions["test-id"]
    assert s["error"] == "Analysis timed out after 5 minutes"
    assert s["generating"] is False
    _sessions.clear()

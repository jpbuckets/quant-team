"""Tests for per-session state isolation (STAB-02, STAB-04)."""
from __future__ import annotations

import pytest


def test_concurrent_sessions_independent():
    """Two sessions have independent generating/progress/error state."""
    pytest.skip("STAB-02: Implement after per-session state refactor")


def test_409_when_session_running():
    """POST /generate returns 409 when a session is already in progress."""
    pytest.skip("STAB-02: Implement after per-session state refactor")


def test_status_returns_progress():
    """GET /status returns current progress during active session (STAB-04)."""
    pytest.skip("STAB-04: Implement after per-session state refactor")


def test_status_returns_error_on_timeout():
    """GET /status returns timeout error message when session times out."""
    pytest.skip("STAB-01/04: Implement after async + per-session state refactor")

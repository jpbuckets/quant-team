"""Tests for bcrypt authentication (STAB-03)."""
from __future__ import annotations

import os
import bcrypt
import pytest
from unittest.mock import patch


def _make_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def test_bcrypt_authenticate():
    """authenticate() returns True for correct password against bcrypt hash."""
    hashed = _make_hash("correct_password")
    env_val = f"test@example.com:{hashed}"
    with patch.dict(os.environ, {"ALLOWED_USERS": env_val}):
        from quant_team.api.auth import authenticate
        assert authenticate("test@example.com", "correct_password") is True


def test_plaintext_rejected():
    """authenticate() returns False when stored value is plaintext (not a bcrypt hash)."""
    env_val = "test@example.com:plaintext_password"
    with patch.dict(os.environ, {"ALLOWED_USERS": env_val}):
        from quant_team.api.auth import authenticate
        # plaintext is not a valid bcrypt hash, checkpw will fail
        assert authenticate("test@example.com", "plaintext_password") is False


def test_wrong_password_rejected():
    """authenticate() returns False for wrong password."""
    hashed = _make_hash("correct_password")
    env_val = f"test@example.com:{hashed}"
    with patch.dict(os.environ, {"ALLOWED_USERS": env_val}):
        from quant_team.api.auth import authenticate
        assert authenticate("test@example.com", "wrong_password") is False


def test_unknown_user_rejected():
    """authenticate() returns False for unknown email."""
    hashed = _make_hash("password")
    env_val = f"known@example.com:{hashed}"
    with patch.dict(os.environ, {"ALLOWED_USERS": env_val}):
        from quant_team.api.auth import authenticate
        assert authenticate("unknown@example.com", "password") is False

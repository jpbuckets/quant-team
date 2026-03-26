"""Tests for bcrypt authentication (STAB-03)."""
from __future__ import annotations

import pytest


def test_bcrypt_authenticate():
    """authenticate() returns True for correct password against bcrypt hash."""
    pytest.skip("STAB-03: Implement after auth.py switched to bcrypt")


def test_plaintext_rejected():
    """authenticate() returns False when stored value is plaintext (not a bcrypt hash)."""
    pytest.skip("STAB-03: Implement after auth.py switched to bcrypt")


def test_wrong_password_rejected():
    """authenticate() returns False for wrong password."""
    pytest.skip("STAB-03: Implement after auth.py switched to bcrypt")


def test_unknown_user_rejected():
    """authenticate() returns False for unknown email."""
    pytest.skip("STAB-03: Implement after auth.py switched to bcrypt")

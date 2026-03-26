"""Simple cookie-based authentication for the dashboard."""

from __future__ import annotations

import hashlib
import hmac
import os
import time

import bcrypt

from fastapi import Request, Response, HTTPException
from fastapi.responses import RedirectResponse


SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
COOKIE_NAME = "qt_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def get_allowed_users() -> dict[str, str]:
    """Parse ALLOWED_USERS from env: 'email:pass,email2:pass2'"""
    raw = os.environ.get("ALLOWED_USERS", "")
    users = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" in entry:
            email, password = entry.split(":", 1)
            users[email.strip().lower()] = password.strip()
    return users


def _sign(data: str) -> str:
    """Create HMAC signature for cookie value."""
    return hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()


def create_session_cookie(email: str) -> str:
    """Create a signed session value."""
    ts = str(int(time.time()))
    payload = f"{email}|{ts}"
    sig = _sign(payload)
    return f"{payload}|{sig}"


def verify_session_cookie(cookie: str) -> str | None:
    """Verify and return email from session cookie, or None if invalid."""
    parts = cookie.split("|")
    if len(parts) != 3:
        return None

    email, ts, sig = parts
    expected = _sign(f"{email}|{ts}")

    if not hmac.compare_digest(sig, expected):
        return None

    # Check expiry
    try:
        created = int(ts)
        if time.time() - created > COOKIE_MAX_AGE:
            return None
    except ValueError:
        return None

    return email


def authenticate(email: str, password: str) -> bool:
    """Check credentials — stored value is a bcrypt hash."""
    users = get_allowed_users()
    stored_hash = users.get(email.lower())
    if stored_hash is None:
        return False
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except (ValueError, TypeError):
        # stored_hash is not a valid bcrypt hash (e.g., still plaintext)
        return False


def get_current_user(request: Request) -> str | None:
    """Extract authenticated user from request cookie."""
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    return verify_session_cookie(cookie)


def require_auth(request: Request) -> str:
    """Dependency that requires authentication. Returns email or redirects."""
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

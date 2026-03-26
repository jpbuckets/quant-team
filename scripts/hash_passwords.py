#!/usr/bin/env python3
"""Generate bcrypt hashes for ALLOWED_USERS env var.

Usage:
    python scripts/hash_passwords.py user@example.com mypassword
    python scripts/hash_passwords.py  # interactive mode
"""
from __future__ import annotations

import sys
import bcrypt


def hash_password(password: str) -> str:
    """Return bcrypt hash string for the given password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def main() -> None:
    if len(sys.argv) == 3:
        email = sys.argv[1]
        password = sys.argv[2]
        hashed = hash_password(password)
        print(f"\nALLOWED_USERS={email}:{hashed}")
        print(f"\nHash: {hashed}")
    elif len(sys.argv) == 1:
        email = input("Email: ").strip()
        password = input("Password: ").strip()
        hashed = hash_password(password)
        print(f"\nALLOWED_USERS={email}:{hashed}")
        print(f"\nHash: {hashed}")
    else:
        print("Usage: python scripts/hash_passwords.py [email] [password]")
        sys.exit(1)


if __name__ == "__main__":
    main()

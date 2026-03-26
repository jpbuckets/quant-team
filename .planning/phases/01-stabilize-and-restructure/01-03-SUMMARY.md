---
phase: 01-stabilize-and-restructure
plan: 03
subsystem: authentication
tags: [security, bcrypt, auth, passwords]
dependency_graph:
  requires: [01-01]
  provides: [bcrypt-password-authentication]
  affects: [quant_team/api/auth.py, tests/test_auth.py]
tech_stack:
  added: [bcrypt>=4.0.0]
  patterns: [bcrypt-hash-verification, try-except-for-invalid-hashes]
key_files:
  created:
    - scripts/hash_passwords.py
  modified:
    - quant_team/api/auth.py
    - .env.example
    - tests/test_auth.py
decisions:
  - bcrypt.checkpw() with try/except used to safely handle both valid hashes and legacy plaintext values
  - hmac import retained — still needed for _sign() and verify_session_cookie()
  - scripts/ directory created to house migration/utility scripts
metrics:
  duration: 69 seconds
  completed_date: "2026-03-26"
  tasks_completed: 1
  files_modified: 4
requirements: [STAB-03]
---

# Phase 01 Plan 03: Bcrypt Password Authentication Summary

**One-liner:** Replaced plaintext HMAC password comparison in auth.py with bcrypt.checkpw() and created a hash helper script for ALLOWED_USERS configuration.

## What Was Built

The authentication system now stores and verifies passwords as bcrypt hashes rather than comparing them in plaintext. A leaked `.env` file no longer exposes user credentials.

**Key changes:**

- `quant_team/api/auth.py` — `authenticate()` now calls `bcrypt.checkpw(password.encode(), stored_hash.encode())` with a `try/except (ValueError, TypeError)` guard that safely rejects any stored value that is not a valid bcrypt hash (including legacy plaintext values)
- `scripts/hash_passwords.py` — CLI tool to generate bcrypt hashes for the `ALLOWED_USERS` env var; accepts `email password` as arguments or runs interactively
- `.env.example` — Updated `ALLOWED_USERS` line to show bcrypt hash format and reference the helper script
- `tests/test_auth.py` — Replaced four `pytest.skip()` stubs with real test implementations covering: correct password, plaintext rejection, wrong password, and unknown user

## Tasks

| # | Name | Status | Commit |
|---|------|--------|--------|
| 1 | Switch authenticate() to bcrypt and create hash helper | Done | 390ae75 |

## Verification Results

```
4 passed in 1.02s
tests/test_auth.py::test_bcrypt_authenticate PASSED
tests/test_auth.py::test_plaintext_rejected PASSED
tests/test_auth.py::test_wrong_password_rejected PASSED
tests/test_auth.py::test_unknown_user_rejected PASSED
```

Additional checks:
- `grep "bcrypt.checkpw" quant_team/api/auth.py` — 1 hit (correct)
- `grep "hmac.compare_digest(stored_password" quant_team/api/auth.py` — 0 hits (plaintext removed)
- `python scripts/hash_passwords.py test@test.com testpass` — outputs `$2b$12$...` hash

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all test stubs replaced with real implementations.

## Self-Check: PASSED

- [x] `quant_team/api/auth.py` exists and contains `bcrypt.checkpw`
- [x] `scripts/hash_passwords.py` exists and contains `bcrypt.hashpw` and `bcrypt.gensalt`
- [x] `.env.example` contains `scripts/hash_passwords.py` reference and `bcrypt hash`
- [x] `tests/test_auth.py` has 4 real test implementations (no skips)
- [x] Commit `390ae75` exists
- [x] All 4 pytest tests pass

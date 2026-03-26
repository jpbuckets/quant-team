# Concerns

## Security

### Critical: Hardcoded Secret Key
- `quant_team/api/auth.py:14` — `SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")`
- Default secret key is used if env var not set — session tokens can be forged
- **Risk:** High — anyone can create valid auth tokens in production

### Critical: Plaintext Password Comparison
- `quant_team/api/auth.py:67-73` — Passwords stored and compared in plaintext
- `hmac.compare_digest` is used (good for timing attacks) but passwords are NOT hashed
- Users file stores raw passwords: `email:password` format
- **Risk:** High — credential exposure if users file is leaked

### Session Cookie Security
- Auth uses cookie-based sessions with HMAC signatures
- No CSRF protection visible
- No session expiration/rotation observed

## Error Handling

### Broad Exception Catching
Heavy use of bare `except Exception:` throughout the codebase:
- `quant_team/trading/portfolio_manager.py` — 6 instances of `except Exception:`
- `quant_team/market/stock_data.py` — 8 instances of `except Exception:`
- `quant_team/orchestrator.py` — 4 instances of `except Exception:`
- **Risk:** Silently swallows errors, makes debugging difficult, masks real failures

## Technical Debt

### No Test Coverage
- Zero test files in the project
- No test framework configured
- All code is untested — changes are high risk

### No Dependency Pinning
- `requirements.txt` may not pin exact versions (needs verification)
- No lock file for reproducible builds

### No Logging Framework
- Error handling catches exceptions but doesn't log them consistently
- No structured logging for debugging or monitoring

## Performance

### Market Data Fetching
- `quant_team/market/stock_data.py` — Multiple try/except blocks around data fetching
- No caching layer visible for market data
- Each request may trigger fresh API calls

### Database
- SQLite used (from `quant_team/database/connection.py`)
- Appropriate for single-user/development but won't scale for concurrent access

## Architecture

### Agent-LLM Coupling
- `quant_team/agents/base.py` — Agents directly call LLM APIs with hardcoded `max_tokens=4096`
- No abstraction layer for swapping LLM providers
- Token limits not configurable

### API Route Organization
- Mix of routes in `quant_team/api/app.py` and separate router files in `quant_team/api/routers/`
- Inconsistent pattern — some endpoints directly in app.py, others properly separated

---
*Mapped: 2026-03-25*

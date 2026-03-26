# External Integrations

**Analysis Date:** 2026-03-25

## APIs & External Services

**AI / LLM:**
- Anthropic Claude API - Powers all four AI agents (Macro Strategist, Quant Analyst, Risk Officer, CIO)
  - SDK/Client: `anthropic` Python package, `anthropic.Anthropic()` client
  - Model: `claude-sonnet-4-20250514` (hardcoded default in `quant_team/agents/base.py`)
  - Auth: `ANTHROPIC_API_KEY` environment variable (read automatically by the Anthropic SDK)
  - Usage: Synchronous `client.messages.create()` calls in `Agent.analyze()` and `Agent.respond()` (`quant_team/agents/base.py`)

**Market Data:**
- Yahoo Finance (via yfinance) - Real-time and historical stock/options market data
  - SDK/Client: `yfinance` Python package, `yf.Ticker()` objects
  - Auth: None required (public API)
  - Usage: OHLCV history, live quotes, options chains (`quant_team/market/stock_data.py`)
  - Data fetched: equity quotes, 3-month OHLCV at 1d interval, options chains for first 3 expirations
  - Indices tracked: SPY, QQQ, IWM, DIA, ^VIX, sector ETFs (XLK, XLV, XLF, XLE, XLY, XLI, XLU, XLRE)

## Data Storage

**Databases:**
- SQLite - Primary and only database
  - Path: `data/dashboard.db` (relative to working directory, created automatically)
  - Connection: `sqlite:///data/dashboard.db` (SQLAlchemy URL in `quant_team/database/connection.py`)
  - Client: SQLAlchemy ORM (`quant_team/database/connection.py`, `quant_team/database/models.py`)
  - Tables: `recommendations`, `portfolio_positions`, `portfolio_snapshots`, `trade_records`, `agent_sessions`, `portfolio_state`
  - Initialization: `init_db()` called at FastAPI lifespan startup, seeds `portfolio_state` row (id=1) if missing

**File Storage:**
- Local filesystem only
  - `data/dashboard.db` - SQLite database
  - `data/ips.md` - Investment Policy Statement (read by orchestrator during sessions, if present)
  - `data/wallet.json` - Present in repo (purpose: legacy/reference data)
  - `data/ips_log.json` - Present in repo (IPS evolution history)
  - `data/sessions/` - Directory present (session artifacts)
  - `logs/` - Log output directory

**Caching:**
- In-memory caches only, no external cache service
  - `StockMarketData._quote_cache` and `._ohlcv_cache` — TTL-based dicts (default 60s) (`quant_team/market/stock_data.py`)

## Authentication & Identity

**Auth Provider:**
- Custom, cookie-based, no third-party provider
  - Implementation: HMAC-SHA256 signed session cookies (`quant_team/api/auth.py`)
  - Cookie name: `qt_session`, max-age 30 days, `httponly=True`
  - Users configured via `ALLOWED_USERS` env var (format: `email:password,email2:password2`)
  - If `ALLOWED_USERS` is unset, auth is skipped entirely — all routes are open
  - Secret: `SECRET_KEY` env var (defaults to `"change-me-in-production"`)
  - Login endpoint: `POST /login` with `email` + `password` form fields (`quant_team/api/app.py`)

## Monitoring & Observability

**Error Tracking:**
- None — no Sentry, Datadog, or equivalent integrated

**Logs:**
- Python `logging` module only
  - Config: `logging.basicConfig(level=INFO)` at startup (`quant_team/api/app.py`)
  - Logger: `quant_team` at `DEBUG` level
  - Output: stdout / `logs/` directory
  - APScheduler job failures are caught and logged as `ERROR` with exception message

## CI/CD & Deployment

**Hosting:**
- Docker container (Dockerfile present at project root)
  - Base: `python:3.12-slim`
  - Entrypoint: `uvicorn quant_team.api.app:app --host 0.0.0.0 --port ${PORT:-8000}`
  - No specific platform targeted in config (generic Docker)

**CI Pipeline:**
- None detected — no GitHub Actions, CircleCI, or equivalent config files present

## Environment Configuration

**Required env vars:**
- `ANTHROPIC_API_KEY` - Anthropic Claude API key (required for any AI agent invocation)
- `SECRET_KEY` - HMAC secret for session cookies (use random string in production)
- `ALLOWED_USERS` - Comma-separated `email:password` pairs (optional; omit to disable auth)

**Optional env vars:**
- `SCHEDULE_ENABLED=true` - Enables APScheduler autonomous cron jobs (disabled by default)
- `PORT` - Override server port in Docker (default `8000`)

**Secrets location:**
- `.env` file at project root (loaded by `python-dotenv` on startup)
- `.env.example` documents all required vars

## Webhooks & Callbacks

**Incoming:**
- None — no webhook endpoints defined

**Outgoing:**
- None — all external calls are request-initiated (Anthropic API, Yahoo Finance)

## Scheduled Operations

APScheduler (active only when `SCHEDULE_ENABLED=true`, US/Eastern timezone, weekdays only):

| Job | Schedule | Function |
|-----|----------|----------|
| Trading session (standard) | 9:35 AM, 12:00 PM ET | `_run_scheduled_session(evolve=False)` |
| Trading session (with IPS evolution) | 3:30 PM ET | `_run_scheduled_session(evolve=True)` |
| Stop-loss check | Every 5 min, 9–15 ET | `_run_stop_check()` |
| Portfolio snapshot | :00 and :30, 9–15 ET | `_run_snapshot()` |

All scheduler logic is in `quant_team/api/app.py`.

---

*Integration audit: 2026-03-25*

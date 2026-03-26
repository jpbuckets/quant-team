# Technology Stack

**Analysis Date:** 2026-03-25

## Languages

**Primary:**
- Python 3.12 - All application code (`quant_team/`, `run.py`)

**Secondary:**
- HTML/Jinja2 - Server-rendered templates (`quant_team/templates/`)
- CSS/JavaScript - Static frontend assets (`quant_team/static/`)

## Runtime

**Environment:**
- Python 3.12 (required: `>=3.12`)

**Package Manager:**
- pip with setuptools
- Lockfile: Not present (no `requirements.txt` or `uv.lock`; `.venv/` present locally)

**Virtual Environment:**
- `.venv/` at project root (local development)

## Frameworks

**Core:**
- FastAPI `>=0.110.0` - HTTP API and server-rendered web dashboard (`quant_team/api/`)
- Uvicorn `>=0.27.0` (standard extras) - ASGI server, entry point via `run.py` and `Dockerfile`

**Templating:**
- Jinja2 `>=3.1.0` - HTML templating for dashboard pages (`quant_team/templates/`)

**Database ORM:**
- SQLAlchemy `>=2.0.0` - ORM and query building (`quant_team/database/`)
- aiosqlite `>=0.20.0` - Async SQLite driver (present as dep; sync usage via SQLAlchemy)

**Scheduling:**
- APScheduler `>=3.10.0` - Cron-based autonomous trading schedule (`quant_team/api/app.py`, `_setup_scheduler()`)

## Key Dependencies

**Critical:**
- `anthropic>=0.40.0` - Claude API client powering all AI agents (`quant_team/agents/base.py`)
- `yfinance>=0.2.30` - Yahoo Finance market data (quotes, OHLCV, options chains) (`quant_team/market/stock_data.py`)

**Data Processing:**
- `pandas>=2.0.0` - OHLCV DataFrame manipulation, indicator computation (`quant_team/market/`)
- `numpy>=1.24.0` - Numerical operations in technical indicators (`quant_team/market/indicators.py`)

**Infrastructure:**
- `python-dotenv>=1.0.0` - `.env` loading at startup (`quant_team/api/app.py`)
- `httpx>=0.25.0` - HTTP client (present as dependency; used transitively by anthropic/yfinance)
- `python-multipart>=0.0.9` - Form data parsing for login endpoint (`quant_team/api/app.py`)

## Configuration

**Environment:**
- Loaded from `.env` via `python-dotenv` at FastAPI startup
- Required vars: `ANTHROPIC_API_KEY`, `SECRET_KEY`, `ALLOWED_USERS`
- Optional vars: `SCHEDULE_ENABLED=true` (enables APScheduler cron jobs)
- Template for required vars: `.env.example`

**Build:**
- `pyproject.toml` - Project metadata, dependencies, build system (setuptools)
- `Dockerfile` - Container build using `python:3.12-slim`, installs package in editable mode, exposes port 8000 with `$PORT` override

## Platform Requirements

**Development:**
- Python 3.12+
- Copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY`
- Run: `python run.py` (uvicorn with `--reload`)

**Production:**
- Docker container: `python:3.12-slim` base
- Port: `$PORT` env var (defaults to 8000)
- Persistent storage: `data/` directory must be mounted (SQLite DB lives at `data/dashboard.db`)
- No external database required — SQLite only

---

*Stack analysis: 2026-03-25*

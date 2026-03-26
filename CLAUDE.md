<!-- GSD:project-start source:PROJECT.md -->
## Project

**Quant Team Trading Platform**

An AI-powered multi-team investment platform where specialized teams of Claude agents analyze markets, produce trade recommendations, and execute trades. Currently a single "quant team" with Macro, Quant, Risk, and CIO agents running sequential round-table analysis on stocks via a FastAPI web dashboard. Evolving toward multiple independent teams (stocks, crypto, options, long-term) with real trade execution.

**Core Value:** The AI agent round-table produces actionable trade decisions that can be automatically executed — analysis without execution is just noise.

### Constraints

- **Tech stack**: Python/FastAPI — keep existing stack, extend don't rewrite
- **AI provider**: Anthropic Claude — all agents use Claude API
- **Database**: SQLite for now — sufficient for single-user
- **Crypto chain**: Solana — Phantom/Drift/Jupiter ecosystem
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12 - All application code (`quant_team/`, `run.py`)
- HTML/Jinja2 - Server-rendered templates (`quant_team/templates/`)
- CSS/JavaScript - Static frontend assets (`quant_team/static/`)
## Runtime
- Python 3.12 (required: `>=3.12`)
- pip with setuptools
- Lockfile: Not present (no `requirements.txt` or `uv.lock`; `.venv/` present locally)
- `.venv/` at project root (local development)
## Frameworks
- FastAPI `>=0.110.0` - HTTP API and server-rendered web dashboard (`quant_team/api/`)
- Uvicorn `>=0.27.0` (standard extras) - ASGI server, entry point via `run.py` and `Dockerfile`
- Jinja2 `>=3.1.0` - HTML templating for dashboard pages (`quant_team/templates/`)
- SQLAlchemy `>=2.0.0` - ORM and query building (`quant_team/database/`)
- aiosqlite `>=0.20.0` - Async SQLite driver (present as dep; sync usage via SQLAlchemy)
- APScheduler `>=3.10.0` - Cron-based autonomous trading schedule (`quant_team/api/app.py`, `_setup_scheduler()`)
## Key Dependencies
- `anthropic>=0.40.0` - Claude API client powering all AI agents (`quant_team/agents/base.py`)
- `yfinance>=0.2.30` - Yahoo Finance market data (quotes, OHLCV, options chains) (`quant_team/market/stock_data.py`)
- `pandas>=2.0.0` - OHLCV DataFrame manipulation, indicator computation (`quant_team/market/`)
- `numpy>=1.24.0` - Numerical operations in technical indicators (`quant_team/market/indicators.py`)
- `python-dotenv>=1.0.0` - `.env` loading at startup (`quant_team/api/app.py`)
- `httpx>=0.25.0` - HTTP client (present as dependency; used transitively by anthropic/yfinance)
- `python-multipart>=0.0.9` - Form data parsing for login endpoint (`quant_team/api/app.py`)
## Configuration
- Loaded from `.env` via `python-dotenv` at FastAPI startup
- Required vars: `ANTHROPIC_API_KEY`, `SECRET_KEY`, `ALLOWED_USERS`
- Optional vars: `SCHEDULE_ENABLED=true` (enables APScheduler cron jobs)
- Template for required vars: `.env.example`
- `pyproject.toml` - Project metadata, dependencies, build system (setuptools)
- `Dockerfile` - Container build using `python:3.12-slim`, installs package in editable mode, exposes port 8000 with `$PORT` override
## Platform Requirements
- Python 3.12+
- Copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY`
- Run: `python run.py` (uvicorn with `--reload`)
- Docker container: `python:3.12-slim` base
- Port: `$PORT` env var (defaults to 8000)
- Persistent storage: `data/` directory must be mounted (SQLite DB lives at `data/dashboard.db`)
- No external database required — SQLite only
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- `snake_case.py` throughout — e.g., `portfolio_manager.py`, `stock_data.py`, `pdt.py`
- Module names are short and descriptive nouns or noun phrases
- Agent files named by role: `cio.py`, `quant.py`, `risk.py`, `macro.py`
- `PascalCase` — e.g., `TradingDesk`, `PortfolioManager`, `RiskChecker`, `PDTChecker`, `StockMarketData`
- ORM models use domain noun names: `Recommendation`, `PortfolioPosition`, `TradeRecord`, `AgentSession`
- Pydantic schemas use `Out` suffix for response models: `RecommendationOut`, `PortfolioOut`, `SessionOut`
- Request models use `Request` suffix: `GenerateRequest`
- `snake_case` for all functions and methods
- Private helpers prefixed with `_`: `_parse_recommendations`, `_auto_execute`, `_find_option_price`, `_sign`, `_run_session`
- Module-level private helpers also prefixed with `_`: `_setup_scheduler`, `_run_scheduled_session`, `_run_stop_check`
- Methods that produce text for agent consumption use suffix `_for_agents`: `get_portfolio_summary_for_agents`, `get_summary_for_agents`
- Boolean query methods use `can_` prefix: `can_day_trade`
- Check methods use `check_` prefix: `check_trade`, `check_stops`
- Predicate methods use `would_be_` prefix: `would_be_day_trade`
- `snake_case` throughout
- Single-letter loop variables avoided in favor of meaningful names (`ticker`, `pos`, `rec`)
- Abbreviations used consistently: `db` for SQLAlchemy session, `pm` for PortfolioManager, `rec` for Recommendation, `pos` for PortfolioPosition
- Constants in `SCREAMING_SNAKE_CASE`: `DEFAULT_WATCHLIST`, `MAX_DAY_TRADES`, `COOKIE_NAME`, `COOKIE_MAX_AGE`
- Prefixed with `_` when mutable internal state: `_engine`, `_SessionLocal`, `_scheduler`, `_generating`, `_progress`, `_last_error`
## Code Style
- No auto-formatter config detected (no `.prettierrc`, `pyproject.toml` has no `[tool.black]` or `[tool.ruff]` section)
- 4-space indentation throughout
- Lines generally kept reasonable in length; some long f-strings are not wrapped
- Trailing commas used in multi-line function arguments and data structures
- Used consistently on all function signatures and return types
- `from __future__ import annotations` present in every module — enables PEP 563 postponed evaluation
- Union types use `X | Y` syntax (Python 3.10+ style), not `Optional[X]` or `Union[X, Y]`
- `None` defaults expressed as `param: Type | None = None`
- Collections annotated as `list[str]`, `dict[str, dict]` (lowercase generics, Python 3.9+ style)
- Single-line module-level docstrings describing the file purpose: `"""Stock market data provider using yfinance."""`
- Class docstrings are single-line: `"""Manages the fictional $10,000 portfolio backed by SQLite."""`
- Method docstrings present for public methods, omitted for obvious private helpers
- No Sphinx or Google-style multi-section docstrings — kept plain prose
## Import Organization
- Relative imports used exclusively within the `quant_team` package
- Grouped with blank lines between standard, third-party, and local
- Named imports preferred over `import module` where specific symbols are needed
- `from sqlalchemy import Column, Integer, ...` — multi-symbol imports on one line for related symbols
- None — uses Python's relative import system (`..`, `...` prefixes)
## Error Handling
- `try/finally` is the dominant pattern for database sessions — ensures `db.close()` always runs:
- External API calls (yfinance, Anthropic) wrapped in bare `except Exception: pass` or `except Exception: continue` to silently skip failures and proceed
- Market data failures degrade gracefully: unavailable data gets a placeholder string rather than raising
- `except json.JSONDecodeError: continue` used in `_parse_recommendations` to skip unparseable blocks
- `HTTPException` raised from FastAPI routers with explicit status codes: `404` for not found, `400` for bad request, `409` for conflict (session already running)
- No custom exception classes — standard `ValueError` used for domain errors (e.g., `raise ValueError(f"No OHLCV data for {ticker}")`)
## Logging
- Each router/module that logs gets its own logger: `logger = logging.getLogger("quant_team")` — all under the same `quant_team` namespace
- `logger.info()` for successful operations and scheduler lifecycle events
- `logger.error()` for caught exceptions in background tasks, with `exc_info=True` for full tracebacks on session failures
- `logger.debug()` used for progress tracking
- No structured logging (no JSON log output)
- Background task errors logged but not re-raised: `logger.error(f"Scheduled session error: {e}")`
## Comments
- Inline comments on non-obvious magic numbers: `# last 5 memories`, `# for spreads`, `# always 1`
- Section dividers in larger functions using `# Step 1:`, `# Step 2:` pattern in `run_trading_session`
- Domain rule explanations: `# A day trade = both BUY and SELL of the same ticker on the same day`
- Override rationale: `# Don't fail the session if evolution fails`
- Module-level docstrings describe the business purpose, not just technical structure
- Self-explanatory code is left without comments
- No commented-out code blocks observed
## Function Design
- Dependency injection pattern: `db: Session` and `market: StockMarketData` passed into constructors rather than created internally
- Optional parameters default to `None` with guard: `tickers: list[str] | None = None` then `tickers = tickers or self.tickers`
- Callback pattern for progress: `on_progress: callable | None = None` with `_progress = on_progress or (lambda *a: None)`
- Methods that can fail return `None` rather than raising: `execute_recommendation` returns `PortfolioPosition | None`
- Validation results returned as `tuple[bool, list[str]]` — `(approved, issues)` pattern in `check_trade`
- Text summaries for agents returned as plain `str` from `_for_agents` methods
## Module Design
- No `__all__` declarations — all public names implicitly exported
- Agent modules expose a single `create()` factory function returning an `Agent` instance
- `__init__.py` files are empty (just markers) except where re-exports are needed
- Single-responsibility observed: `RiskChecker` only validates, `PDTChecker` only tracks day trades, `PortfolioManager` only manages positions
- `TradingDesk` acts as an orchestrator/facade, assembling all components
- Used for simple value objects: `Message` in `agents/base.py`, `RiskLimits` in `trading/risk.py`
- `@dataclass` without `frozen=True` — mutable by default
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern
## Layers
```
```
## Data Flow
## Key Abstractions
### TradingDesk (`quant_team/orchestrator.py`)
### BaseAgent (`quant_team/agents/base.py`)
### PortfolioManager (`quant_team/trading/portfolio_manager.py`)
## Entry Points
- **`run.py`** — Main application entry point, starts FastAPI server
- **`quant_team/api/app.py`** — FastAPI application with HTML and API routes
- **APScheduler** — Autonomous scheduled sessions (configured in app startup)
## Scheduling
- Autonomous trading sessions run on weekdays at 9:35am, 12:00pm, 3:30pm ET
- Uses APScheduler integrated with the FastAPI application
- Sessions run the full orchestrator pipeline without user interaction
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

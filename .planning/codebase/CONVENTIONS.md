# Coding Conventions

**Analysis Date:** 2026-03-25

## Naming Patterns

**Files:**
- `snake_case.py` throughout — e.g., `portfolio_manager.py`, `stock_data.py`, `pdt.py`
- Module names are short and descriptive nouns or noun phrases
- Agent files named by role: `cio.py`, `quant.py`, `risk.py`, `macro.py`

**Classes:**
- `PascalCase` — e.g., `TradingDesk`, `PortfolioManager`, `RiskChecker`, `PDTChecker`, `StockMarketData`
- ORM models use domain noun names: `Recommendation`, `PortfolioPosition`, `TradeRecord`, `AgentSession`
- Pydantic schemas use `Out` suffix for response models: `RecommendationOut`, `PortfolioOut`, `SessionOut`
- Request models use `Request` suffix: `GenerateRequest`

**Functions and Methods:**
- `snake_case` for all functions and methods
- Private helpers prefixed with `_`: `_parse_recommendations`, `_auto_execute`, `_find_option_price`, `_sign`, `_run_session`
- Module-level private helpers also prefixed with `_`: `_setup_scheduler`, `_run_scheduled_session`, `_run_stop_check`
- Methods that produce text for agent consumption use suffix `_for_agents`: `get_portfolio_summary_for_agents`, `get_summary_for_agents`
- Boolean query methods use `can_` prefix: `can_day_trade`
- Check methods use `check_` prefix: `check_trade`, `check_stops`
- Predicate methods use `would_be_` prefix: `would_be_day_trade`

**Variables:**
- `snake_case` throughout
- Single-letter loop variables avoided in favor of meaningful names (`ticker`, `pos`, `rec`)
- Abbreviations used consistently: `db` for SQLAlchemy session, `pm` for PortfolioManager, `rec` for Recommendation, `pos` for PortfolioPosition
- Constants in `SCREAMING_SNAKE_CASE`: `DEFAULT_WATCHLIST`, `MAX_DAY_TRADES`, `COOKIE_NAME`, `COOKIE_MAX_AGE`

**Module-level globals:**
- Prefixed with `_` when mutable internal state: `_engine`, `_SessionLocal`, `_scheduler`, `_generating`, `_progress`, `_last_error`

## Code Style

**Formatting:**
- No auto-formatter config detected (no `.prettierrc`, `pyproject.toml` has no `[tool.black]` or `[tool.ruff]` section)
- 4-space indentation throughout
- Lines generally kept reasonable in length; some long f-strings are not wrapped
- Trailing commas used in multi-line function arguments and data structures

**Type Annotations:**
- Used consistently on all function signatures and return types
- `from __future__ import annotations` present in every module — enables PEP 563 postponed evaluation
- Union types use `X | Y` syntax (Python 3.10+ style), not `Optional[X]` or `Union[X, Y]`
- `None` defaults expressed as `param: Type | None = None`
- Collections annotated as `list[str]`, `dict[str, dict]` (lowercase generics, Python 3.9+ style)

**Docstrings:**
- Single-line module-level docstrings describing the file purpose: `"""Stock market data provider using yfinance."""`
- Class docstrings are single-line: `"""Manages the fictional $10,000 portfolio backed by SQLite."""`
- Method docstrings present for public methods, omitted for obvious private helpers
- No Sphinx or Google-style multi-section docstrings — kept plain prose

## Import Organization

**Order (observed pattern):**
1. `from __future__ import annotations` (always first)
2. Standard library imports (`json`, `re`, `os`, `time`, `logging`, `pathlib`, `datetime`, `dataclasses`)
3. Third-party imports (`anthropic`, `pandas`, `numpy`, `yfinance`, `fastapi`, `sqlalchemy`, `dotenv`)
4. Local relative imports (`from ..database.models import ...`, `from .auth import ...`)

**Style:**
- Relative imports used exclusively within the `quant_team` package
- Grouped with blank lines between standard, third-party, and local
- Named imports preferred over `import module` where specific symbols are needed
- `from sqlalchemy import Column, Integer, ...` — multi-symbol imports on one line for related symbols

**Path Aliases:**
- None — uses Python's relative import system (`..`, `...` prefixes)

## Error Handling

**Strategy:**
- `try/finally` is the dominant pattern for database sessions — ensures `db.close()` always runs:
  ```python
  db = get_db()
  try:
      # ... work ...
  finally:
      db.close()
  ```
- External API calls (yfinance, Anthropic) wrapped in bare `except Exception: pass` or `except Exception: continue` to silently skip failures and proceed
- Market data failures degrade gracefully: unavailable data gets a placeholder string rather than raising
- `except json.JSONDecodeError: continue` used in `_parse_recommendations` to skip unparseable blocks
- `HTTPException` raised from FastAPI routers with explicit status codes: `404` for not found, `400` for bad request, `409` for conflict (session already running)
- No custom exception classes — standard `ValueError` used for domain errors (e.g., `raise ValueError(f"No OHLCV data for {ticker}")`)

## Logging

**Framework:** Python stdlib `logging`

**Setup:** Configured once in `quant_team/api/app.py`:
```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("quant_team")
logger.setLevel(logging.DEBUG)
```

**Patterns:**
- Each router/module that logs gets its own logger: `logger = logging.getLogger("quant_team")` — all under the same `quant_team` namespace
- `logger.info()` for successful operations and scheduler lifecycle events
- `logger.error()` for caught exceptions in background tasks, with `exc_info=True` for full tracebacks on session failures
- `logger.debug()` used for progress tracking
- No structured logging (no JSON log output)
- Background task errors logged but not re-raised: `logger.error(f"Scheduled session error: {e}")`

## Comments

**When to Comment:**
- Inline comments on non-obvious magic numbers: `# last 5 memories`, `# for spreads`, `# always 1`
- Section dividers in larger functions using `# Step 1:`, `# Step 2:` pattern in `run_trading_session`
- Domain rule explanations: `# A day trade = both BUY and SELL of the same ticker on the same day`
- Override rationale: `# Don't fail the session if evolution fails`
- Module-level docstrings describe the business purpose, not just technical structure

**When Not to Comment:**
- Self-explanatory code is left without comments
- No commented-out code blocks observed

## Function Design

**Size:** Functions vary widely — `run_trading_session` is ~130 lines (orchestration), pure calculations are 3-10 lines

**Parameters:**
- Dependency injection pattern: `db: Session` and `market: StockMarketData` passed into constructors rather than created internally
- Optional parameters default to `None` with guard: `tickers: list[str] | None = None` then `tickers = tickers or self.tickers`
- Callback pattern for progress: `on_progress: callable | None = None` with `_progress = on_progress or (lambda *a: None)`

**Return Values:**
- Methods that can fail return `None` rather than raising: `execute_recommendation` returns `PortfolioPosition | None`
- Validation results returned as `tuple[bool, list[str]]` — `(approved, issues)` pattern in `check_trade`
- Text summaries for agents returned as plain `str` from `_for_agents` methods

## Module Design

**Exports:**
- No `__all__` declarations — all public names implicitly exported
- Agent modules expose a single `create()` factory function returning an `Agent` instance

**Package Init Files:**
- `__init__.py` files are empty (just markers) except where re-exports are needed

**Class Responsibilities:**
- Single-responsibility observed: `RiskChecker` only validates, `PDTChecker` only tracks day trades, `PortfolioManager` only manages positions
- `TradingDesk` acts as an orchestrator/facade, assembling all components

**Dataclasses:**
- Used for simple value objects: `Message` in `agents/base.py`, `RiskLimits` in `trading/risk.py`
- `@dataclass` without `frozen=True` — mutable by default

---

*Convention analysis: 2026-03-25*

# Phase 2: Market Data Routing - Research

**Researched:** 2026-03-26
**Domain:** Multi-source market data routing (yfinance / ccxt / Jupiter Price API)
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | Crypto team can fetch Solana token prices via Jupiter Price API | Jupiter Price API v3 endpoint documented; requires free API key from portal.jup.ag |
| DATA-02 | Crypto team can fetch CEX market data (OHLCV, tickers) via ccxt | ccxt 4.5.44 already installed; `fetch_ohlcv` and `fetch_ticker` documented |
| DATA-03 | Stock team can fetch equity market data via yfinance (must not regress) | `StockMarketData` class exists and works; router wraps it without touching it |
| DATA-04 | Market data is routed to the correct source based on team's asset class | `TeamConfig.asset_class` field already present; router dispatches on that value |
</phase_requirements>

---

## Summary

Phase 2 introduces a `MarketDataRouter` that dispatches to asset-class-specific data providers based on `TeamConfig.asset_class`. The router is the primary new abstraction: it wraps the existing `StockMarketData` unchanged, adds a new `CryptoMarketData` class backed by ccxt + Jupiter Price API v3, and returns a normalized `MarketSnapshot` text that the orchestrator passes into agent context.

The key integration facts discovered during research: **Jupiter Price API v3 requires a free API key** obtained from portal.jup.ag — the old `price.jup.ag` endpoint is deprecated. The API key goes in the `X-API-Key` header. ccxt 4.5.44 is already installed in the project's venv. The `TeamConfig.asset_class` field is already set on both existing YAML configs (`"stocks"` for quant). The orchestrator currently hardcodes `StockMarketData()` directly — this needs to be replaced with a router-dispatched provider.

**Primary recommendation:** Build `CryptoMarketData` as a thin class over ccxt + Jupiter httpx calls. Build `MarketDataRouter` as a simple dispatch function on `asset_class`. Wire the router into `TeamOrchestrator.__init__` replacing the hardcoded `StockMarketData()` instance. Add `data/teams/crypto.yaml` to prove end-to-end routing.

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python/FastAPI — keep existing stack, extend don't rewrite
- **AI provider**: Anthropic Claude — all agents use Claude API
- **Database**: SQLite for now — sufficient for single-user
- **Crypto chain**: Solana — Phantom/Drift/Jupiter ecosystem
- **No LangChain/LangGraph/CrewAI** — plain Python + Anthropic SDK only
- **GSD workflow**: Use `/gsd:execute-phase` for all repo edits; no direct edits outside GSD
- **Naming**: `snake_case` files, `PascalCase` classes, `_for_agents` suffix for text-summary methods
- **Imports**: Relative imports within `quant_team` package; `from __future__ import annotations` in every module
- **Error handling**: External API calls wrapped in `except Exception`; market data failures degrade gracefully (placeholder string, not raise)
- **Logging**: `logger = logging.getLogger("quant_team")` per module; `logger.info` for lifecycle events

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ccxt | 4.5.44 (installed) | CEX OHLCV, tickers, order books | 100+ exchanges, unified API, already in venv |
| httpx | 0.28.1 (installed) | Jupiter Price API HTTP calls | Already a project dependency; async-capable |
| yfinance | 1.2.0 (installed) | Stock equity data (unchanged) | Existing provider, no changes needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas | >=2.0.0 (installed) | OHLCV DataFrame handling | ccxt returns list-of-lists; convert to DataFrame for `compute_all()` compat |

### New Packages Required
None. All required libraries (`ccxt`, `httpx`, `pandas`) are already installed in the project venv and declared in `pyproject.toml`.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Jupiter Price API v3 | CoinGecko / CoinMarketCap | Jupiter is on-chain accurate for Solana DeFi tokens; CoinGecko lags for small-cap SPL tokens |
| ccxt for CEX OHLCV | Raw Binance REST API | ccxt is already installed and provides exchange-agnostic interface |

**Installation:** No new `pip install` commands needed — ccxt and httpx are already in the venv.

**Version verification:** Confirmed installed: `ccxt==4.5.44`, `httpx==0.28.1`, `yfinance==1.2.0`.

---

## Architecture Patterns

### Recommended Project Structure
```
quant_team/market/
├── __init__.py          # unchanged
├── stock_data.py        # unchanged — StockMarketData class
├── indicators.py        # unchanged — compute_all()
├── crypto_data.py       # NEW — CryptoMarketData class
└── router.py            # NEW — MarketDataRouter (dispatch + MarketSnapshot)
data/teams/
├── quant.yaml           # unchanged
└── crypto.yaml          # NEW — crypto team config (asset_class: crypto)
```

### Pattern 1: MarketDataRouter Dispatch
**What:** A `MarketDataRouter` class receives `TeamConfig` at construction and returns a uniform market context string from `get_market_context(tickers)`. Internally it instantiates either `StockMarketData` or `CryptoMarketData` based on `config.asset_class`.

**When to use:** Everywhere the orchestrator currently calls `self.market = StockMarketData()`.

**Example:**
```python
# quant_team/market/router.py
from __future__ import annotations

from .stock_data import StockMarketData
from .crypto_data import CryptoMarketData
from ..teams.registry import TeamConfig


class MarketDataRouter:
    """Routes market data fetches to the correct provider based on asset class."""

    def __init__(self, config: TeamConfig):
        self.config = config
        if config.asset_class == "stocks":
            self._provider = StockMarketData()
        elif config.asset_class == "crypto":
            self._provider = CryptoMarketData()
        else:
            raise ValueError(f"Unknown asset_class: {config.asset_class!r}")

    def get_market_context(self, tickers: list[str]) -> str:
        """Return formatted market context string for agent consumption."""
        return self._provider.get_market_summary(tickers)

    def fetch_ohlcv(self, ticker: str, period: str = "3mo", interval: str = "1d"):
        return self._provider.fetch_ohlcv(ticker, period, interval)

    def fetch_quote(self, ticker: str) -> dict:
        return self._provider.fetch_quote(ticker)
```

### Pattern 2: CryptoMarketData — Dual Source
**What:** `CryptoMarketData` fetches spot prices from Jupiter Price API v3 (on-chain, accurate for SPL tokens) and OHLCV candlestick data from a CEX via ccxt (Binance by default).

**Interface contract:** Same public method signatures as `StockMarketData` — `fetch_quote(ticker)`, `fetch_ohlcv(ticker, period, interval)`, `get_market_summary(tickers)` — so the router can call either provider identically.

**Example:**
```python
# quant_team/market/crypto_data.py — Jupiter Price API v3
import httpx

JUPITER_PRICE_URL = "https://api.jup.ag/price/v3"

async def _fetch_jupiter_prices(mint_addresses: list[str], api_key: str) -> dict:
    """Fetch USD prices for SPL token mint addresses from Jupiter Price API v3."""
    ids = ",".join(mint_addresses)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{JUPITER_PRICE_URL}/price",
            params={"ids": ids},
            headers={"X-API-Key": api_key},
        )
        resp.raise_for_status()
        return resp.json()  # {"data": {"<mint>": {"price": "...", ...}}}
```

```python
# ccxt OHLCV — synchronous (matches StockMarketData pattern)
import ccxt

exchange = ccxt.binance()  # or configurable exchange name
ohlcv = exchange.fetch_ohlcv("SOL/USDT", "1d", limit=90)
# Returns: [[timestamp, open, high, low, close, volume], ...]
# Convert to DataFrame with columns: open, high, low, close, volume
```

### Pattern 3: Ticker Symbol Mapping (Crypto)
**What:** Crypto teams use Solana token mint addresses (base58 strings) as canonical IDs for Jupiter, but CEX symbols like `"SOL/USDT"` for ccxt. A mapping dict in `crypto_data.py` translates between them.

**Why it matters:** The YAML watchlist for a crypto team will contain human-readable tokens (e.g., `"SOL"`, `"JUP"`, `"BONK"`). Jupiter needs mint addresses; ccxt needs `"SOL/USDT"` style pairs.

**Example:**
```python
# Well-known Solana token mints (HIGH confidence — stable addresses)
KNOWN_MINTS = {
    "SOL":  "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "JUP":  "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
}

def ticker_to_mint(symbol: str) -> str | None:
    return KNOWN_MINTS.get(symbol.upper())

def ticker_to_ccxt_pair(symbol: str, quote: str = "USDT") -> str:
    return f"{symbol.upper()}/{quote}"
```

### Pattern 4: Orchestrator Wire-Up
**What:** Replace the hardcoded `self.market = StockMarketData()` in `TeamOrchestrator.__init__` with `self.market = MarketDataRouter(config)`. The `PortfolioManager` constructor also receives `self.market` — no signature change needed since it only uses `fetch_quote()`.

**Change in `orchestrator.py`:**
```python
# Before (hardcoded):
from .market.stock_data import StockMarketData
self.market = StockMarketData()

# After (routed):
from .market.router import MarketDataRouter
self.market = MarketDataRouter(config)
```

The orchestrator's `run_trading_session` also calls `self.market.fetch_ohlcv()` and `self.market.get_options_summary()`. Options summary is stock-specific — `CryptoMarketData` should return an empty string or `None` from `get_options_summary()` so the call degrades gracefully.

### Anti-Patterns to Avoid
- **Branching on `asset_class` inside the orchestrator** — the whole point of the router is to push that logic out; if `orchestrator.py` has `if config.asset_class == "crypto"` blocks, the abstraction has failed.
- **Using `price.jup.ag` (old URL)** — deprecated as of 2025; use `api.jup.ag/price/v3`. Requests to the old URL will fail.
- **Caching Jupiter quotes across sessions** — quote freshness is not as critical here as for execution (Phase 3), but TTL caching (60s) is appropriate; never cache indefinitely.
- **Making ccxt calls async with `asyncio.to_thread`** — ccxt's Python library is synchronous; the orchestrator is async. Wrap ccxt calls in `asyncio.to_thread()` or call from a sync provider that the async orchestrator awaits via `run_in_executor`. Simpler: keep `CryptoMarketData` synchronous (like `StockMarketData`) and use sync httpx for Jupiter in this phase. Async httpx needed only if called inside a running event loop.
- **Hardcoding Binance as the only CEX** — use a configurable exchange name in the crypto team YAML; default to `"binance"`. Do not hardcode inside `CryptoMarketData.__init__`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CEX OHLCV data | Custom Binance REST client | `ccxt.binance().fetch_ohlcv()` | Rate limiting, auth, pagination, error codes already handled |
| SPL token price | On-chain RPC price math | Jupiter Price API v3 | Jupiter aggregates all DEX swaps with outlier filtering — impossible to replicate reliably |
| Symbol → mint lookup | Query on-chain token registry | Static `KNOWN_MINTS` dict for Phase 2 | Token registry lookup is overkill; watchlist is small and known at config time |
| HTTP retry logic | Custom retry loop | httpx built-in transport retries or `tenacity` | Edge cases (429, connection reset, timeout) are already handled |

**Key insight:** ccxt's value is that exchange-specific quirks (rate limits, symbol formats, API auth) are abstracted away. Never bypass it for a "simpler" raw request.

---

## Common Pitfalls

### Pitfall 1: Jupiter Price API `price.jup.ag` Deprecation
**What goes wrong:** Code using `https://price.jup.ag/v6/price` or `https://price.jup.ag/v4/price` returns 404 or connection errors.
**Why it happens:** Jupiter migrated to `https://api.jup.ag/price/v3` in 2025 and shut down the old domain.
**How to avoid:** Use `https://api.jup.ag/price/v3/price` with `X-API-Key` header. Get key from portal.jup.ag (free tier available).
**Warning signs:** `httpx.HTTPStatusError: 404` on price fetch; any URL containing `price.jup.ag`.

### Pitfall 2: Missing Jupiter API Key
**What goes wrong:** HTTP 401 or 403 on all Jupiter price requests.
**Why it happens:** Jupiter Price API v3 requires an API key even for the free tier.
**How to avoid:** Add `JUPITER_API_KEY` to `.env.example` and `.env`; read it from environment in `CryptoMarketData.__init__`. Fail with a clear error message if the key is missing, rather than silently returning empty prices.
**Warning signs:** `401 Unauthorized` from `api.jup.ag`; missing env var at startup.

### Pitfall 3: ccxt Symbol Format
**What goes wrong:** `exchange.fetch_ohlcv("SOL", "1d")` raises `BadSymbol` — ccxt expects `"SOL/USDT"` not `"SOL"`.
**Why it happens:** All ccxt markets use `BASE/QUOTE` format.
**How to avoid:** Always construct `f"{symbol}/USDT"` when calling ccxt. The `ticker_to_ccxt_pair()` helper handles this.
**Warning signs:** `ccxt.errors.BadSymbol` exception during OHLCV fetch.

### Pitfall 4: ccxt in Async Context (Event Loop Conflict)
**What goes wrong:** Calling `exchange.fetch_ohlcv()` (sync) directly from an async `run_trading_session()` blocks the event loop.
**Why it happens:** ccxt's standard library is synchronous. The orchestrator is async.
**How to avoid:** Either (a) keep `CryptoMarketData.fetch_ohlcv()` synchronous and call it from the orchestrator with `await asyncio.to_thread(self.market.fetch_ohlcv, ticker, ...)`, or (b) use ccxt's async variant `ccxt.async_support.binance`. Option (a) is simpler and consistent with `StockMarketData` (also synchronous).
**Warning signs:** Analysis sessions freeze; `RuntimeError: This event loop is already running`.

### Pitfall 5: `get_options_summary` Called on Crypto Provider
**What goes wrong:** `orchestrator.py` calls `self.market.get_options_summary(ticker)` in a loop for the top 3 tickers. If `CryptoMarketData` doesn't implement this, `AttributeError` breaks the session.
**Why it happens:** `StockMarketData` has `get_options_summary()` but crypto assets don't have options chains in Phase 2.
**How to avoid:** Implement `get_options_summary()` on `CryptoMarketData` as a stub that returns `""`. The orchestrator's existing `except Exception: pass` block will catch it if it raises, but returning empty string is cleaner.
**Warning signs:** `AttributeError: 'CryptoMarketData' object has no attribute 'get_options_summary'`.

### Pitfall 6: PortfolioManager Passed StockMarketData Type
**What goes wrong:** `PortfolioManager(db, self.market)` — if `PortfolioManager` type-checks or uses attributes specific to `StockMarketData`, it breaks when given a `MarketDataRouter`.
**Why it happens:** `PortfolioManager` receives the market object and calls `fetch_quote()` on it.
**How to avoid:** `MarketDataRouter.fetch_quote()` must be implemented and delegate to the underlying provider. Verify `PortfolioManager` only calls `fetch_quote()` — confirmed from codebase read.
**Warning signs:** `AttributeError` on `PortfolioManager` internal calls during BUY execution.

---

## Code Examples

Verified patterns from official sources:

### ccxt OHLCV Fetch (Binance)
```python
# Source: ccxt official docs / github.com/ccxt/ccxt examples
import ccxt

exchange = ccxt.binance()
# symbol must be "BASE/QUOTE" format
ohlcv = exchange.fetch_ohlcv("SOL/USDT", timeframe="1d", limit=90)
# Returns: [[timestamp_ms, open, high, low, close, volume], ...]

import pandas as pd
df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
df.set_index("timestamp", inplace=True)
# Now df is compatible with compute_all() in indicators.py
```

### ccxt Ticker (Live Price)
```python
# Source: ccxt docs
ticker = exchange.fetch_ticker("SOL/USDT")
price = ticker["last"]       # last traded price
bid   = ticker["bid"]
ask   = ticker["ask"]
volume = ticker["quoteVolume"]  # 24h volume in USDT
```

### Jupiter Price API v3
```python
# Source: dev.jup.ag/llms.txt (verified 2026-03-26)
# Endpoint: GET https://api.jup.ag/price/v3/price
# Auth: X-API-Key header (free key from portal.jup.ag)
# Params: ids = comma-separated mint addresses or "SOL", up to 100 per request

import httpx, os

JUPITER_PRICE_URL = "https://api.jup.ag/price/v3/price"

def fetch_jupiter_prices(mints: list[str]) -> dict[str, float]:
    """Fetch USD prices for given mint addresses. Returns {mint: price_usd}."""
    api_key = os.environ.get("JUPITER_API_KEY", "")
    ids = ",".join(mints)
    try:
        resp = httpx.get(
            JUPITER_PRICE_URL,
            params={"ids": ids},
            headers={"X-API-Key": api_key},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return {mint: float(entry["price"]) for mint, entry in data.items() if entry}
    except Exception:
        return {}
```

### Orchestrator Wire-Up
```python
# quant_team/orchestrator.py — replace hardcoded StockMarketData
# Before:
# from .market.stock_data import StockMarketData
# self.market = StockMarketData()

# After:
from .market.router import MarketDataRouter
self.market = MarketDataRouter(config)
```

### crypto.yaml — Crypto Team Config
```yaml
team_id: crypto
name: Crypto DeFi Team
asset_class: crypto
execution_backend: paper
exchange: binance       # ccxt exchange name
watchlist:
  - SOL
  - JUP
  - BONK
risk_limits:
  max_position_pct: 20.0
  max_exposure_pct: 80.0
  max_drawdown_pct: 20.0
  max_options_pct: 0.0
schedule_cron:
  - {hour: 8, minute: 0}
  - {hour: 16, minute: 0}
agents:
  - name: OnChain
    title: On-Chain Analyst
    # ... system_prompt
  - name: DeFi
    title: DeFi Strategist
    # ... system_prompt
  - name: Risk
    title: Chief Risk Officer
    # ... system_prompt
  - name: CIO
    title: Chief Investment Officer
    # ... system_prompt
```

Note: `exchange` is a new optional `TeamConfig` field — either add it to `TeamConfig` dataclass or read it from a `metadata` dict. Simplest: add `exchange: str = "binance"` to `TeamConfig`.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `price.jup.ag/v6/price` | `api.jup.ag/price/v3/price` | 2025 migration | New endpoint requires API key; old URL is dead |
| `price.jup.ag/v4/price` | `api.jup.ag/price/v3/price` | 2025 migration | Same deprecation |
| No-auth Jupiter Price API | `X-API-Key` header required | 2025 | Free key from portal.jup.ag — one-time setup |

**Deprecated/outdated:**
- `https://price.jup.ag` domain: fully deprecated; any code using it will fail with 404/connection error
- Jupiter Python SDKs (`jupiter-py`, `jupiverse`): third-party wrappers lag behind API changes; use `httpx` directly against the REST API

---

## Open Questions

1. **`exchange` field in TeamConfig**
   - What we know: `TeamConfig` does not currently have an `exchange` field; crypto team needs to specify which CEX to use for OHLCV
   - What's unclear: Whether to add `exchange: str = "binance"` to `TeamConfig` dataclass, or read it from a `metadata: dict` bag, or hardcode binance for Phase 2
   - Recommendation: Add `exchange: str = "binance"` to `TeamConfig` dataclass with a sensible default — minimal change, YAML-configurable

2. **Jupiter API key management**
   - What we know: Free tier key available at portal.jup.ag; must be passed as `X-API-Key` header
   - What's unclear: Rate limit numbers for free tier not publicly documented; whether free tier is sufficient for analysis cadence (a few calls per session, a few sessions per day)
   - Recommendation: Add `JUPITER_API_KEY` to `.env.example`; treat missing key as graceful degradation (empty price data, log warning) rather than startup failure

3. **Task prompt for crypto team**
   - What we know: `orchestrator.py` hardcodes a stock-specific task prompt mentioning "US stock market", "PDT rules", "$10,000 portfolio"
   - What's unclear: Whether the orchestrator should generate asset-class-aware prompts or whether the agent system prompts handle framing
   - Recommendation: Make the task prompt asset-class-aware in Phase 2 — minimal branching on `config.asset_class` in the task string is acceptable since it's a string, not a dispatch pattern

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| ccxt | DATA-02 CEX OHLCV | Yes | 4.5.44 | — |
| httpx | DATA-01 Jupiter Price API | Yes | 0.28.1 | — |
| yfinance | DATA-03 Stock data | Yes | 1.2.0 | — |
| pandas | OHLCV DataFrame | Yes | installed | — |
| JUPITER_API_KEY env var | DATA-01 | Not yet set | — | Degrade gracefully; log warning |

**Missing dependencies with no fallback:** None — all Python packages are installed.

**Missing dependencies with fallback:**
- `JUPITER_API_KEY`: Not yet in `.env` — add to `.env.example`; if absent at runtime, crypto price fetches return empty data with a logged warning rather than crashing.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7+ with pytest-asyncio |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | Jupiter price fetch returns dict with price for known mint | unit (mock httpx) | `pytest tests/test_crypto_data.py::test_jupiter_price_fetch -x` | Wave 0 |
| DATA-01 | Missing JUPITER_API_KEY degrades gracefully (returns {}) | unit | `pytest tests/test_crypto_data.py::test_jupiter_missing_key -x` | Wave 0 |
| DATA-02 | ccxt OHLCV returns DataFrame compatible with compute_all() | unit (mock ccxt) | `pytest tests/test_crypto_data.py::test_ccxt_ohlcv_dataframe -x` | Wave 0 |
| DATA-02 | ccxt ticker returns dict with 'price' key | unit (mock ccxt) | `pytest tests/test_crypto_data.py::test_ccxt_ticker_quote -x` | Wave 0 |
| DATA-03 | StockMarketData still callable through router for stocks asset_class | unit | `pytest tests/test_router.py::test_stocks_routes_to_stock_provider -x` | Wave 0 |
| DATA-04 | MarketDataRouter dispatches to CryptoMarketData for crypto asset_class | unit | `pytest tests/test_router.py::test_crypto_routes_to_crypto_provider -x` | Wave 0 |
| DATA-04 | MarketDataRouter raises ValueError for unknown asset_class | unit | `pytest tests/test_router.py::test_unknown_asset_class_raises -x` | Wave 0 |
| DATA-03 | Existing quant team orchestrator session produces market context (no regression) | integration | `pytest tests/test_orchestrator.py -x` | Yes (existing) |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_crypto_data.py` — covers DATA-01 (Jupiter) and DATA-02 (ccxt), using mocked httpx and mocked ccxt exchange
- [ ] `tests/test_router.py` — covers DATA-03 (stocks no-regression) and DATA-04 (routing dispatch)

*(Existing test infrastructure — pytest, pytest-asyncio, conftest.py — covers all framework needs. Only new test files are needed.)*

---

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `quant_team/orchestrator.py`, `quant_team/market/stock_data.py`, `quant_team/teams/registry.py`, `data/teams/quant.yaml`, `pyproject.toml` — confirmed exact versions, hardcoded `StockMarketData()` instantiation, `TeamConfig.asset_class` field
- `dev.jup.ag/llms.txt` (fetched 2026-03-26) — confirmed `api.jup.ag/price/v3/price` endpoint, `X-API-Key` header requirement, free tier availability at portal.jup.ag
- ccxt GitHub examples (`github.com/ccxt/ccxt/blob/master/examples/py/binance-fetch-ohlcv.py`) — confirmed `fetch_ohlcv` signature and return format

### Secondary (MEDIUM confidence)
- WebSearch: Jupiter 2025 migration notice — confirmed `price.jup.ag` deprecated, new endpoint at `api.jup.ag`
- `dev.jup.ag/docs/api-setup` (fetched 2026-03-26) — confirmed free/pro/ultra tier structure and `x-api-key` header

### Tertiary (LOW confidence)
- Jupiter free tier rate limits: exact numbers not publicly documented — treat as unverified; monitor for 429 responses in practice

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages already installed; versions confirmed from venv
- Architecture: HIGH — `MarketDataRouter` pattern is straightforward OOP; `TeamConfig.asset_class` hook point already exists
- Jupiter API: MEDIUM — endpoint URL and auth confirmed; rate limit numbers unverified
- ccxt usage: HIGH — stable library with confirmed installed version and well-documented API
- Pitfalls: HIGH — Jupiter deprecation confirmed from official docs; ccxt async pitfall is well-known Python pattern

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (Jupiter API endpoints are stable once migrated; ccxt is stable)

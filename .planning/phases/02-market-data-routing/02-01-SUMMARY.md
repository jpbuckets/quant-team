---
phase: 02-market-data-routing
plan: 01
subsystem: market-data
tags: [crypto, ccxt, jupiter, routing, tdd]
dependency_graph:
  requires: []
  provides: [CryptoMarketData, MarketDataRouter, TeamConfig.exchange]
  affects: [quant_team/market/, quant_team/teams/registry.py]
tech_stack:
  added: [ccxt, httpx (Jupiter Price API v3)]
  patterns: [provider-dispatch, TDD red-green, TTL caching, graceful degradation]
key_files:
  created:
    - quant_team/market/crypto_data.py
    - quant_team/market/router.py
    - tests/test_crypto_data.py
    - tests/test_router.py
  modified:
    - quant_team/teams/registry.py
decisions:
  - "CryptoMarketData fetches prices via Jupiter Price API v3 (api.jup.ag/price/v3/price) with X-API-Key header; graceful degradation when key missing"
  - "KNOWN_MINTS static dict covers SOL/USDC/JUP/BONK for Phase 2; on-chain registry lookup deferred to Phase 3"
  - "fetch_options_chain returns empty structure and get_options_summary returns empty string for crypto in Phase 2"
  - "MarketDataRouter raises ValueError for unknown asset_class values — fail-fast design"
  - "TeamConfig.exchange field added with 'binance' default; YAML-configurable per team"
metrics:
  duration_minutes: 25
  completed_date: "2026-03-26"
  tasks_completed: 2
  files_changed: 5
---

# Phase 2 Plan 01: CryptoMarketData Provider and MarketDataRouter Summary

**One-liner:** CryptoMarketData wraps Jupiter Price API v3 and ccxt for Solana/CEX data; MarketDataRouter dispatches to stock or crypto provider based on TeamConfig.asset_class.

## What Was Built

### Task 1: CryptoMarketData provider (TDD)

Created `quant_team/market/crypto_data.py` implementing the full `StockMarketData` interface contract:

- `fetch_ohlcv(ticker, period, interval)` — calls ccxt `exchange.fetch_ohlcv(SOL/USDT, ...)`, converts list-of-lists to a `pd.DataFrame` with `DatetimeIndex` and `[open, high, low, close, volume]` columns, compatible with `compute_all()` from `indicators.py`
- `fetch_quote(ticker)` — tries Jupiter Price API first (mint address lookup via `KNOWN_MINTS`), falls back to ccxt ticker; returns standardized dict matching `StockMarketData.fetch_quote()` shape
- `fetch_multiple_quotes(tickers)` — loops with per-ticker try/except for graceful degradation
- `fetch_options_chain(ticker)` — returns `{"ticker": t, "expirations": [], "chains": {}}` (crypto has no options in Phase 2)
- `get_market_summary(tickers)` — formats "# Crypto Market Summary" text for agent consumption
- `get_options_summary(ticker)` — returns `""` (empty string)
- `fetch_jupiter_prices(mints)` — module-level function; reads `JUPITER_API_KEY` from env, logs warning if absent, degrades to `{}` on any error

11 tests in `tests/test_crypto_data.py` cover all behaviors with mocked httpx and ccxt.

### Task 2: MarketDataRouter + TeamConfig.exchange (TDD)

Created `quant_team/market/router.py`:
- `MarketDataRouter(config: TeamConfig)` instantiates `StockMarketData()` for `asset_class="stocks"` and `CryptoMarketData(exchange_name=config.exchange)` for `asset_class="crypto"`; raises `ValueError` for unknown values
- All 6 public methods delegate directly to `self._provider`

Modified `quant_team/teams/registry.py`:
- Added `exchange: str = "binance"` field to `TeamConfig` dataclass (after `execution_backend`)
- Added `exchange=data.get("exchange", "binance")` in `TeamRegistry._parse()`

12 tests in `tests/test_router.py` cover routing dispatch, delegation, and exchange field behavior.

## Test Results

```
50 passed, 1 skipped, 18 warnings (full suite)
- test_crypto_data.py: 11 passed
- test_router.py: 12 passed
- test_registry.py: 6 passed (no regressions)
- all other existing tests: unchanged
```

## Commits

| Hash | Message |
|------|---------|
| 66de43f | test(02-01): add failing tests for CryptoMarketData |
| fa5c01b | feat(02-01): implement CryptoMarketData with Jupiter Price API v3 and ccxt |
| 4a0724a | test(02-01): add failing tests for MarketDataRouter and TeamConfig.exchange |
| 867775f | feat(02-01): add MarketDataRouter and exchange field to TeamConfig |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All implemented methods return real data (mocked only in tests). `fetch_options_chain` and `get_options_summary` return intentional empty values per plan spec — crypto has no options chains in Phase 2. These are documented behaviors, not stubs: the plan explicitly calls for empty returns.

## Self-Check: PASSED

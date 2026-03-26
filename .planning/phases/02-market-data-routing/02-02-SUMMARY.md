---
phase: 02-market-data-routing
plan: 02
subsystem: orchestration
tags: [market-data, routing, crypto, orchestrator, portfolio-manager]
dependency_graph:
  requires: [02-01]
  provides: [router-wired-orchestrator, crypto-team-config]
  affects: [quant_team/orchestrator.py, quant_team/trading/portfolio_manager.py, data/teams/crypto.yaml, .env.example]
tech_stack:
  added: []
  patterns: [MarketDataRouter delegation, asset-class-aware task prompts, YAML team configs]
key_files:
  created:
    - data/teams/crypto.yaml
  modified:
    - quant_team/orchestrator.py
    - quant_team/trading/portfolio_manager.py
    - .env.example
decisions:
  - "Orchestrator passes TeamConfig to MarketDataRouter — router selects provider transparently"
  - "PDT note excluded from crypto task prompt — PDT rules are equity-specific regulations"
  - "crypto.yaml uses exchange: binance matching TeamConfig.exchange default"
metrics:
  duration: 8
  completed_date: "2026-03-26"
  tasks_completed: 2
  files_modified: 4
---

# Phase 02 Plan 02: Wire MarketDataRouter into Application Layer Summary

**One-liner:** Router-wired orchestrator with asset-class-aware prompts and full crypto team YAML config for SOL/JUP/BONK trading.

## What Was Built

Connected the MarketDataRouter abstraction (built in Plan 01) to the existing application layer. The orchestrator now instantiates `MarketDataRouter(config)` instead of the hardcoded `StockMarketData()`, routing crypto teams to Jupiter/ccxt and stock teams to yfinance transparently. A complete crypto team YAML config was added proving end-to-end routing works.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wire MarketDataRouter into orchestrator and update PortfolioManager type | 4fd19ae | quant_team/orchestrator.py, quant_team/trading/portfolio_manager.py |
| 2 | Add crypto.yaml team config and JUPITER_API_KEY to .env.example | fa4b5ce | data/teams/crypto.yaml, .env.example |

## Changes Made

### orchestrator.py
- Replaced `from .market.stock_data import StockMarketData` with `from .market.router import MarketDataRouter`
- Replaced `self.market = StockMarketData()` with `self.market = MarketDataRouter(config)`
- Added asset-class-aware `task_prompt` branching: crypto path excludes PDT note (equity-specific); stock path unchanged

### portfolio_manager.py
- Updated import from `StockMarketData` to `MarketDataRouter`
- Updated `__init__` type hint: `market: MarketDataRouter`
- No functional changes — `fetch_quote` and `fetch_options_chain` delegate correctly through router

### data/teams/crypto.yaml
- Full team config: `team_id: crypto`, `asset_class: crypto`, `exchange: binance`
- 4 agents: OnChain Analyst, DeFi Strategist, Chief Risk Officer, Chief Investment Officer
- Watchlist: SOL, JUP, BONK
- Risk limits: max_position_pct 20%, max_exposure_pct 80%, max_drawdown_pct 20%, max_options_pct 0%
- Schedule: 8:00 and 16:00 daily

### .env.example
- Added `JUPITER_API_KEY=` with comment pointing to portal.jup.ag

## Verification Results

- Full test suite: 50 passed, 1 skipped, 0 failures
- TeamRegistry loads both teams: `['crypto', 'quant']`
- MarketDataRouter with `asset_class='stocks'` returns `StockMarketData` provider
- `grep -r "StockMarketData" quant_team/orchestrator.py` — no matches
- `grep -r "StockMarketData" quant_team/trading/portfolio_manager.py` — no matches

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None — all paths are wired. The crypto team config is fully functional; actual crypto market data fetching depends on `JUPITER_API_KEY` environment variable (graceful degradation if missing, documented in Plan 01).

## Self-Check: PASSED

- /Users/justinprappas/trading/data/teams/crypto.yaml — FOUND
- /Users/justinprappas/trading/quant_team/orchestrator.py — FOUND (MarketDataRouter wired)
- /Users/justinprappas/trading/quant_team/trading/portfolio_manager.py — FOUND (type updated)
- /Users/justinprappas/trading/.env.example — FOUND (JUPITER_API_KEY added)
- Commits 4fd19ae and fa4b5ce — FOUND

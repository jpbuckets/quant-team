---
phase: 03-paper-trading-execution
plan: "02"
subsystem: trading-execution
tags: [execution-router, teams-api, paper-trading, tdd]
dependency_graph:
  requires: ["03-01"]
  provides: ["ExecutionRouter", "Teams API", "execution mode toggle"]
  affects: ["quant_team/orchestrator.py", "quant_team/api/app.py"]
tech_stack:
  added: []
  patterns: ["router pattern (matches MarketDataRouter)", "hot-swap backend via update_backend", "TDD red-green cycle"]
key_files:
  created:
    - quant_team/trading/execution_router.py
    - quant_team/api/routers/teams.py
    - tests/test_execution_router.py
  modified:
    - quant_team/orchestrator.py
    - quant_team/api/app.py
decisions:
  - "ExecutionRouter follows MarketDataRouter pattern exactly — same constructor, same delegation style"
  - "update_backend() hot-swaps executor at runtime; takes effect on next session (orchestrator reads config.execution_backend)"
  - "Teams API valid_modes=['paper'] hard-coded — expand when AlpacaExecutor/SolanaExecutor added"
  - "Orchestrator _auto_execute retains all risk/PDT logic; only final execution calls replaced"
metrics:
  duration_minutes: 3
  completed_date: "2026-03-26"
  tasks_completed: 2
  files_changed: 5
---

# Phase 03 Plan 02: ExecutionRouter and Teams API Summary

ExecutionRouter dispatching to PaperExecutor with per-team mode toggle API via TDD.

## What Was Built

### ExecutionRouter (`quant_team/trading/execution_router.py`)

New module following the MarketDataRouter pattern. Selects executor based on `config.execution_backend`:
- `"paper"` → `PaperExecutor()`
- Future: `"alpaca"` → `AlpacaExecutor()`, `"solana"` → `SolanaExecutor()`

Provides `update_backend(backend)` for hot-swap without server restart.

### Orchestrator refactor (`quant_team/orchestrator.py`)

- Added `self.execution = ExecutionRouter(config)` in `__init__`
- `_auto_execute` BUY now calls `self.execution.execute_buy(rec, self.market, self.db, self.config.team_id)`
- `_auto_execute` SELL now calls `self.execution.execute_sell(rec, self.market, self.db, self.config.team_id)`
- All risk checks and PDT checks preserved exactly — only the final execution step changed
- Removed direct `portfolio.execute_recommendation` and `portfolio.sell_by_ticker` calls

### Teams API (`quant_team/api/routers/teams.py`)

Two endpoints:
- `GET /api/teams` — lists all team configs with `execution_backend` field
- `PATCH /api/teams/{team_id}/execution-mode` — toggles `execution_backend` at runtime (404 on unknown team)

Registered in `app.py` at `prefix="/api/teams"`.

### Tests (`tests/test_execution_router.py`)

7 tests covering:
1. ExecutionRouter with `execution_backend="paper"` creates PaperExecutor
2. `update_backend("paper")` hot-swaps executor instance
3. Unknown backend raises ValueError
4. `update_backend("unknown")` raises ValueError
5. GET /api/teams returns all teams with `execution_backend`
6. PATCH /api/teams/{id}/execution-mode returns 200 with updated backend
7. PATCH with invalid team_id returns 404

## Test Results

- 63 tests pass, 1 skipped (pre-existing skip), 0 failures
- Full suite regression-free

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All execution routing is wired through PaperExecutor which performs real DB writes (paper simulated fills). No placeholder data flows to UI.

## Self-Check: PASSED

- execution_router.py: FOUND
- teams.py: FOUND
- test_execution_router.py: FOUND
- 03-02-SUMMARY.md: FOUND
- commit 4328ef4 (Task 1): FOUND
- commit 49702e5 (RED tests): FOUND
- commit b144500 (Task 2): FOUND

---
phase: 03-paper-trading-execution
verified: 2026-03-26T00:00:00Z
status: gaps_found
score: 6/7 must-haves verified
re_verification: false
gaps:
  - truth: "Toggling a team from paper to live (or back) takes effect on the next session without restarting"
    status: failed
    reason: "The toggle endpoint modifies an in-memory TeamConfig from an ephemeral TeamRegistry instance. The next session (both on-demand via /api/recommendations/generate and scheduled via APScheduler) creates a fresh TeamRegistry() from YAML, discarding the in-memory change. There is no shared registry singleton, no YAML write-back, and no global mutable state between requests. The toggle survives only for the lifetime of the PATCH request handler's local TeamRegistry object."
    artifacts:
      - path: "quant_team/api/routers/teams.py"
        issue: "update_execution_mode modifies config.execution_backend on a locally-created TeamRegistry instance (lines 43-48). That instance is garbage-collected after the request. No persistence mechanism."
      - path: "quant_team/api/routers/recommendations.py"
        issue: "_run_session (line 122) calls TeamRegistry() fresh, re-loading YAML. Toggle change is invisible here."
      - path: "quant_team/api/app.py"
        issue: "_run_scheduled_session (line 86) calls TeamRegistry() fresh. Toggle change is invisible to the scheduler."
    missing:
      - "TeamRegistry must be a module-level singleton (created once, shared across requests) OR the toggle endpoint must write the updated execution_backend back to the YAML file OR a mutable global store of overrides must be passed to each new TeamRegistry"
      - "Simplest fix: make TeamRegistry a cached singleton — e.g., module-level _registry: TeamRegistry | None = None with a get_registry() accessor, so the toggle endpoint's mutation is seen by the next session"
human_verification:
  - test: "Confirm EXEC-03 runtime behavior"
    expected: "PATCH /api/teams/quant/execution-mode with mode='paper' followed by a manual /api/recommendations/generate session should show the toggled backend in effect (currently impossible to verify with live mode since only paper exists, but the data path gap can be confirmed by adding debug logging)"
    why_human: "Only one valid mode ('paper') exists in current implementation. There is no 'live' backend to toggle TO, so the broken toggle cannot be observed functionally. The bug only becomes observable when a second execution backend is added."
---

# Phase 03: Paper Trading Execution — Verification Report

**Phase Goal:** All teams paper-trade by default and log every would-be trade with full detail; live mode is toggleable per team
**Verified:** 2026-03-26
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | PaperExecutor simulates trades without sending real orders | VERIFIED | `execution.py` implements full simulation: fetches quote via `market.fetch_quote()`, creates `PortfolioPosition`, writes `TradeRecord`, deducts/returns cash — no real order API called |
| 2 | Every paper trade creates a log entry with symbol, side, quantity, and simulated fill price | VERIFIED | `TradeRecord` written on every BUY and SELL with `ticker`, `action`, `quantity`, `price`, `notional`, and `reasoning="[PAPER] ..."`. Logger also emits `[PAPER] BUY/SELL qty ticker @ $price` |
| 3 | ExecutionResult captures all details of what would have happened | VERIFIED | `ExecutionResult` dataclass has `success`, `trade_record`, `position`, `reason`, `simulated_price` — all populated in both buy and sell paths |
| 4 | A stock team's execution routes to PaperExecutor when execution_backend is paper | VERIFIED | `ExecutionRouter._build_executor("paper")` returns `PaperExecutor()`. `data/teams/quant.yaml` has `execution_backend: paper`. `TeamOrchestrator.__init__` builds `ExecutionRouter(config)` |
| 5 | A crypto team's execution routes to PaperExecutor when execution_backend is paper | VERIFIED | `data/teams/crypto.yaml` has `execution_backend: paper`. Same router path applies since asset_class does not affect executor selection |
| 6 | Toggling a team from paper to live (or back) takes effect on the next session without restarting | FAILED | Toggle endpoint modifies an ephemeral in-memory `TeamConfig`. Both `_run_session` and `_run_scheduled_session` create `new TeamRegistry()` from YAML on each call, discarding any in-memory changes. See Gaps section. |
| 7 | The orchestrator uses ExecutionRouter instead of direct portfolio manipulation | VERIFIED | `orchestrator.py` line 19 imports `ExecutionRouter`, line 53 constructs `self.execution = ExecutionRouter(config)`. `_auto_execute` calls `self.execution.execute_buy` (line 326) and `self.execution.execute_sell` (line 268). Grep confirms `portfolio.execute_recommendation` and `portfolio.sell_by_ticker` are absent from `_auto_execute`. |

**Score:** 6/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `quant_team/trading/execution.py` | BaseExecutor ABC, PaperExecutor, ExecutionResult dataclass | VERIFIED | 233 lines. All three classes present and substantive. `ExecutionResult` has 5 fields. `BaseExecutor` has 2 abstract methods. `PaperExecutor` has full buy/sell implementation with DB writes. |
| `tests/test_execution.py` | Tests for PaperExecutor behavior | VERIFIED | 244 lines. 6 test cases covering buy success, insufficient cash, sell success, no open position, result fields, and `[PAPER]` prefix. |
| `quant_team/trading/execution_router.py` | ExecutionRouter dispatching to correct executor by team config | VERIFIED | 58 lines. `ExecutionRouter` class with `_build_executor`, `execute_buy`, `execute_sell`, `update_backend`. Imports `PaperExecutor`. |
| `quant_team/api/routers/teams.py` | API endpoint for listing teams and toggling execution mode | VERIFIED (WIRED, toggle logic has persistence gap) | 51 lines. `GET /` and `PATCH /{team_id}/execution-mode` present. `ExecutionModeRequest` with `mode` field. Wired into `app.py`. |
| `tests/test_execution_router.py` | Tests for routing and mode toggle | VERIFIED | 165 lines. 7 tests covering `paper` backend creates `PaperExecutor`, hot-swap, unknown backend raises ValueError, and 3 Teams API tests. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `execution.py` | `market/router.py` | `PaperExecutor` calls `market.fetch_quote()` | WIRED | Lines 68-69 (buy) and 164-165 (sell) call `market.fetch_quote(rec.ticker)` |
| `execution.py` | `database/models.py` | `PaperExecutor` writes `TradeRecord` entries | WIRED | Lines 107-118 (buy) and 196-207 (sell) construct and `db.add(trade)` |
| `execution_router.py` | `execution.py` | Router instantiates `PaperExecutor` based on config | WIRED | Line 27: `return PaperExecutor()` in `_build_executor` |
| `orchestrator.py` | `execution_router.py` | Orchestrator delegates `_auto_execute` to `ExecutionRouter` | WIRED | Line 19 import, line 53 `self.execution = ExecutionRouter(config)`, lines 268 and 326 delegate buy/sell |
| `api/routers/teams.py` | `teams/registry.py` | Toggle endpoint updates `TeamConfig.execution_backend` in registry | PARTIAL | Endpoint correctly finds `config = registry.get(team_id)` and sets `config.execution_backend = body.mode` — but `registry` is a per-request local instance. Mutation is not visible to subsequent session calls. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `PaperExecutor.execute_buy` | `TradeRecord.reasoning` | `"[PAPER] " + rec.reasoning` | Yes — pre-populated by orchestrator from CIO agent response | FLOWING |
| `PaperExecutor.execute_buy` | `PortfolioState.cash` | `_get_state(db, team_id)` — real DB query | Yes — fetches or creates row in `portfolio_states` table | FLOWING |
| `PaperExecutor.execute_buy` | `current_price` | `market.fetch_quote(rec.ticker)["price"]` | Yes — routes to `StockMarketData` or `CryptoMarketData` | FLOWING |
| `ExecutionRouter._executor` | executor backend | `config.execution_backend` from `TeamConfig` | Yes — loaded from `data/teams/*.yaml` at `TeamRegistry` creation | FLOWING (initial session); NOT PERSISTED (after toggle) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| PaperExecutor imports cleanly | `.venv/bin/python -c "from quant_team.trading.execution import ExecutionResult, BaseExecutor, PaperExecutor; print('OK')"` | OK | PASS |
| ExecutionRouter imports cleanly | `.venv/bin/python -c "from quant_team.trading.execution_router import ExecutionRouter; print('OK')"` | OK | PASS |
| Teams router imports cleanly | `.venv/bin/python -c "from quant_team.api.routers.teams import router; print('OK')"` | OK | PASS |
| Phase 03 test suite (13 tests) | `.venv/bin/python -m pytest tests/test_execution.py tests/test_execution_router.py -v` | 13 passed | PASS |
| Full test suite (no regressions) | `.venv/bin/python -m pytest tests/ -q` | 63 passed, 1 skipped | PASS |
| Commits exist (5 referenced) | `git log --oneline` | All 5 hashes found: b578207, 6bf7125, 4328ef4, 49702e5, b144500 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| EXEC-01 | 03-01-PLAN.md | All teams start in paper trading mode by default | SATISFIED | `TeamConfig.execution_backend` defaults to `"paper"` (registry.py line 41). Both `data/teams/quant.yaml` and `data/teams/crypto.yaml` explicitly set `execution_backend: paper`. `ExecutionRouter` defaults to `PaperExecutor` when backend is `"paper"`. |
| EXEC-02 | 03-01-PLAN.md | Paper trades are logged with what would have happened (symbol, side, quantity, price) | SATISFIED | `TradeRecord` written by `PaperExecutor` with `ticker`, `action` (BUY/SELL), `quantity`, `price`, `notional`, `reasoning="[PAPER] ..."`. Logger also emits structured `[PAPER]` info line. |
| EXEC-03 | 03-02-PLAN.md | Live vs paper mode is toggleable per team | PARTIALLY SATISFIED | API endpoint `PATCH /api/teams/{team_id}/execution-mode` exists and responds correctly. However, the toggle modifies an ephemeral `TeamRegistry` instance; the next session re-loads config from YAML, losing the change. Toggle does not persist across requests. |
| EXEC-04 | 03-02-PLAN.md | Execution is routed to the correct backend based on team configuration | SATISFIED | `ExecutionRouter._build_executor()` selects `PaperExecutor` when `config.execution_backend == "paper"`. `TeamOrchestrator` passes team config to `ExecutionRouter`. Teams read from YAML with explicit `execution_backend` field. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `quant_team/trading/execution.py` | 91, 182, 188 | `datetime.utcnow()` (deprecated) | Info | Deprecation warning only; functionality unaffected |
| `quant_team/tests/test_execution.py` | 176 | `Query.get()` (SQLAlchemy 2.0 legacy API) | Info | Deprecation warning only; test still passes |
| `quant_team/api/routers/teams.py` | 44, 48 | Toggle modifies local `TeamRegistry` instance | Blocker | EXEC-03 gap — toggle does not persist to subsequent sessions |
| `quant_team/api/routers/recommendations.py` | 123 | `registry.get("quant")` hardcoded team ID | Warning | On-demand sessions always run as `"quant"` team regardless of team multi-tenancy |

### Human Verification Required

#### 1. EXEC-03 Runtime Toggle Behavior

**Test:** Start the server, PATCH `/api/teams/quant/execution-mode` with `{"mode": "paper"}`, then trigger a session via POST `/api/recommendations/generate` and observe whether the team that executes uses the in-memory-toggled config or a freshly-loaded config.
**Expected:** If the registry were a singleton, the toggle would persist. With the current implementation, the toggle has no observable effect since both modes are "paper" anyway.
**Why human:** Only one valid mode exists. The bug becomes a user-visible problem only when a second execution backend (Alpaca, Solana) is added. Automating this requires a live server or a second executor implementation.

---

## Gaps Summary

One gap blocks complete EXEC-03 satisfaction: the execution mode toggle is ephemeral.

**Root cause:** `TeamRegistry` is instantiated fresh (`new TeamRegistry()`) on every session invocation — both in `_run_session` (on-demand API) and `_run_scheduled_session` (scheduler). The toggle endpoint creates its own local `TeamRegistry`, mutates the in-memory `TeamConfig`, and that mutation disappears when the request completes. The next session loads a pristine config from YAML.

**Blast radius:** Currently zero, because only `"paper"` is a valid mode and both teams are already set to `"paper"` in YAML. The bug will surface when a live executor is added (Phase 5 / v2 LIVE-01 or LIVE-02).

**Fix options (in order of simplicity):**
1. Make `TeamRegistry` a module-level singleton via a `get_registry()` factory that caches the instance — all callers share the same in-memory state.
2. Write the toggle change back to the YAML file in `update_execution_mode`, so the next `TeamRegistry()` load picks it up.
3. Keep ephemeral registries but add a global `_execution_mode_overrides: dict[str, str]` that `TeamRegistry.get()` checks before returning config.

All other phase goals are fully achieved with no regressions.

---

_Verified: 2026-03-26_
_Verifier: Claude (gsd-verifier)_

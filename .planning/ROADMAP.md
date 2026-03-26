# Roadmap: Quant Team Trading Platform

## Overview

Starting from a broken single-team stock analyzer, this roadmap evolves the platform into a stable, multi-team AI trading system capable of paper-trading stocks and crypto through independent team configurations. Phase 1 fixes critical existing bugs and builds the team-aware foundation everything else depends on. Phase 2 wires asset-class-specific market data. Phase 3 adds paper trading execution with routing. Phase 4 delivers the multi-team dashboard that makes it all observable. Live execution is v2 scope.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Stabilize and Restructure** - Fix critical bugs and build team-aware foundation (team registry, scoped DB, parameterized orchestrator) (completed 2026-03-26)
- [x] **Phase 2: Market Data Routing** - Wire asset-class-specific data feeds so each team type gets correct market context (completed 2026-03-26)
- [ ] **Phase 3: Paper Trading Execution** - Add paper execution framework with per-team mode toggle and routed execution
- [ ] **Phase 4: Multi-Team Dashboard** - Build team-selector UI, per-team portfolio views, and cross-team summary

## Phase Details

### Phase 1: Stabilize and Restructure
**Goal**: The existing quant team runs reliably through a team-aware architecture with no hanging, no race conditions, and no security bugs
**Depends on**: Nothing (first phase)
**Requirements**: STAB-01, STAB-02, STAB-03, STAB-04, TEAM-01, TEAM-02, TEAM-03, TEAM-04, TEAM-05
**Success Criteria** (what must be TRUE):
  1. Clicking Analyze always completes or shows a clear timeout error within 5 minutes — it never hangs indefinitely
  2. Running two analysis sessions concurrently does not corrupt either session's state or produce duplicate records
  3. User passwords are stored and compared as bcrypt hashes — plaintext is never persisted or read
  4. A live progress indicator appears during analysis so the user knows something is happening
  5. A new crypto or options team can be added by writing a YAML config file — no Python code changes required in the orchestrator
**Plans:** 5/5 plans complete
Plans:
- [x] 01-01-PLAN.md — Test infrastructure + install dependencies (pytest, bcrypt, pyyaml)
- [x] 01-02-PLAN.md — Async agent pipeline + per-session state + progress (STAB-01, STAB-02, STAB-04)
- [x] 01-03-PLAN.md — Bcrypt password authentication (STAB-03)
- [x] 01-04-PLAN.md — Database team_id migration + WAL mode (TEAM-02)
- [x] 01-05-PLAN.md — Team registry + dynamic orchestrator + scheduling (TEAM-01, TEAM-03, TEAM-04, TEAM-05)

### Phase 2: Market Data Routing
**Goal**: Each team type fetches market data from the correct source based on its asset class configuration
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. A crypto team session receives Solana token prices from Jupiter Price API, not yfinance
  2. A crypto team session receives OHLCV candlestick data from a CEX via ccxt
  3. A stock team session continues to receive equity data from yfinance without regression
  4. Pointing a team at a different asset class in its config automatically routes it to the correct data source
**Plans:** 2/2 plans complete
Plans:
- [x] 02-01-PLAN.md — CryptoMarketData provider + MarketDataRouter dispatch + tests
- [x] 02-02-PLAN.md — Wire router into orchestrator + crypto.yaml + env config

### Phase 3: Paper Trading Execution
**Goal**: All teams paper-trade by default and log every would-be trade with full detail; live mode is toggleable per team
**Depends on**: Phase 2
**Requirements**: EXEC-01, EXEC-02, EXEC-03, EXEC-04
**Success Criteria** (what must be TRUE):
  1. Every team starts in paper mode — no real orders are sent unless live mode is explicitly enabled for that team
  2. Each paper trade creates a log entry showing symbol, side, quantity, and price that would have executed
  3. Toggling a team from paper to live (or back) takes effect on the next session without restarting the server
  4. Execution is routed through an ExecutionRouter that dispatches to the correct executor based on team configuration (unified PaperExecutor for all teams in v1; asset-class-specific live executors deferred to v2)
**Plans:** 1/2 plans executed
Plans:
- [x] 03-01-PLAN.md — Execution framework with PaperExecutor + trade logging (EXEC-01, EXEC-02)
- [ ] 03-02-PLAN.md — ExecutionRouter + orchestrator wiring + mode toggle API (EXEC-03, EXEC-04)

### Phase 4: Multi-Team Dashboard
**Goal**: The user can view and manage all teams from one web interface with per-team and aggregate visibility
**Depends on**: Phase 3
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04
**Success Criteria** (what must be TRUE):
  1. The main dashboard shows all configured teams and the user can select any team to view its detail page
  2. Each team's detail page shows its current positions, running P&L, and full session history
  3. A cross-team summary page shows aggregate portfolio value and exposure across all active teams
  4. Every team's detail page clearly displays whether that team is running in paper or live mode
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Stabilize and Restructure | 5/5 | Complete   | 2026-03-26 |
| 2. Market Data Routing | 2/2 | Complete   | 2026-03-26 |
| 3. Paper Trading Execution | 1/2 | In Progress|  |
| 4. Multi-Team Dashboard | 0/TBD | Not started | - |

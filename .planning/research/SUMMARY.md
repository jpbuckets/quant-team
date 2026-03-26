# Project Research Summary

**Project:** AI Multi-Team Trading Platform
**Domain:** Autonomous AI trading system (stocks + crypto/DeFi)
**Researched:** 2026-03-25
**Confidence:** MEDIUM overall

## Executive Summary

This project evolves an existing single-team AI stock trading platform into a multi-team autonomous trading system spanning stocks, crypto/DeFi (Solana), and options. The existing codebase (FastAPI + SQLAlchemy + Anthropic SDK + yfinance) is sound and should not be replaced — the work is primarily structural: extracting a team-aware orchestration layer, scoping all DB models by `team_id`, and adding asset-class-specific market data and execution routers. The multi-agent pattern (plain Python + Anthropic SDK) is correct and should not be swapped for LangChain, LangGraph, or CrewAI.

The recommended approach is to build in four stages: (1) fix critical existing bugs and restructure the codebase into team-aware abstractions without changing behavior, (2) add the crypto team with paper execution, (3) wire live execution for both Alpaca (stocks) and Solana (crypto via Jupiter), and (4) extend into options and perpetual futures. Paper trading must precede live execution for every team. The Alpaca REST API is strongly preferred over IBKR for stock execution — IBKR's TWS/IB Gateway daemon is a deployment blocker in any containerized environment.

The key risks are three existing bugs that must be fixed in Phase 1 (hanging analysis, global state race condition, plaintext password storage) and a set of Solana-specific traps that will destroy portfolio state if not addressed before crypto execution goes live (wrong commitment level, stale Jupiter quotes, uninitialized Drift accounts). The `team_id` scoping on all database models is the single architectural decision that must be correct from day one — retrofitting it after a second team is added is painful.

## Key Findings

### Recommended Stack

The existing Python 3.12 / FastAPI / SQLAlchemy / anthropic / yfinance / APScheduler stack is retained as-is. New packages are narrowly scoped to what each new execution domain requires: `solders` + `solana` + `driftpy` for Solana primitives and Drift Protocol, `alpaca-py` for stock broker execution, `ccxt` for crypto OHLCV data, and `base58` for keypair loading. Jupiter swaps use the v6 REST API via `httpx` — no dedicated SDK exists that tracks API changes reliably.

**Core technologies:**
- `solders` + `solana`: Solana keypair signing and RPC client — only viable Python Solana stack
- `driftpy`: Drift Protocol perpetuals SDK — preferred over raw anchorpy to avoid hand-encoding Anchor discriminators
- Jupiter v6 REST API (httpx): Spot token swaps — more stable than any third-party wrapper
- `alpaca-py`: Stock/ETF order execution — pure REST, no local daemon required (unlike IBKR)
- `ccxt`: CEX crypto OHLCV data for market context — 100+ exchanges, unified API
- `AsyncAnthropic`: Already in the anthropic package — needed for async agent calls to fix the hang bug

See `.planning/research/STACK.md` for full version requirements.

### Expected Features

The existing quant stocks team is baseline. Every feature beyond it is additive.

**Must have (table stakes):**
- Team registry + `team_id` scoped DB models — foundation every other feature depends on
- Parameterized TeamOrchestrator — replace hardcoded 4-agent TradingDesk with config-driven version
- Per-team portfolio tracking — separate P&L, positions, sessions per team
- Paper trading mode — all teams start here before live execution
- Crypto price feeds (Jupiter Price API + ccxt) — yfinance cannot cover Solana tokens
- Jupiter spot execution — basic crypto buy/sell on Solana
- Alpaca stock execution — paper then live for the existing quant team

**Should have (differentiators):**
- Drift Protocol perpetuals — leverage and short positions on Solana
- Cross-team risk management — global exposure limits, correlation detection
- Options-specific analysis (Greeks, strategy recognition, expiration tracking)
- Team performance analytics (Sharpe, drawdown, win rate, agent contribution)

**Defer to v2+:**
- Backtesting engine — massive complexity, not a stated need
- Options on crypto — extremely niche
- Multi-chain crypto (Ethereum/BSC) — Solana-only is the right constraint
- Streaming WebSockets — polling is sufficient for analysis cadence

See `.planning/research/FEATURES.md` for full anti-features list.

### Architecture Approach

The target architecture has 8 components that replace or evolve current monolithic pieces. The key structural insight is to use routers — `MarketDataRouter` and `ExecutionRouter` — that dispatch to asset-class-specific implementations and return normalized results. This keeps the `TeamOrchestrator` asset-class-agnostic and avoids the anti-pattern of branching on asset class inside the orchestrator. `TeamRegistry` is YAML-backed config (no database), and `PortfolioManager` gains `team_id` filtering on all queries.

**Major components:**
1. `TeamRegistry` — YAML-backed config; owns `TeamConfig` + `AgentSpec` dataclasses
2. `TeamOrchestrator` — replaces `TradingDesk`; constructs agents from config, delegates via routers
3. `MarketDataRouter` — dispatches to `StockMarketData` / `CryptoMarketData` / `OptionsMarketData`; returns normalized `MarketSnapshot`
4. `ExecutionRouter` — dispatches to `PaperExecutor` / `AlpacaExecutor` / `SolanaExecutor`; returns normalized `ExecutionResult`
5. `PortfolioManager` — same interface, scoped by `team_id`
6. `RiskChecker` — supplied per-team limits via `TeamConfig.risk_limits`; PDT check runs only for stock teams
7. `Scheduler` — iterates registry on startup; registers per-team cron jobs
8. `API Layer` — team-scoped URL structure: `/api/teams/{team_id}/sessions`

SQLite WAL mode must be enabled before concurrent team sessions. See `.planning/research/ARCHITECTURE.md` for data flow diagram.

### Critical Pitfalls

1. **Hanging analysis (existing bug)** — sync `anthropic.Anthropic()` blocks the async FastAPI event loop with no timeout. Fix: switch to `AsyncAnthropic` with `asyncio.wait_for()` 300-second timeout. Fix in Phase 1 before any new work.

2. **Global state race condition (existing bug)** — `_generating`, `_progress`, `_last_error` are module-level globals; concurrent team sessions will stomp each other. Fix: per-session state objects keyed by session ID; SQLite WAL mode. Fix in Phase 1.

3. **Shared PortfolioState singleton** — `PortfolioState(id=1)` means all teams share one portfolio row. Fix: add `team_id` to all portfolio models from day one. Never retrofit this later.

4. **Solana transaction finality** — using `processed` commitment causes ghost positions (transactions can roll back). Always use `confirmed` or `finalized`; poll for confirmation before updating local state.

5. **Jupiter stale quotes** — quotes expire in seconds; using analysis-time quotes for execution causes failed swaps. Fetch fresh quote immediately before building each swap transaction; never cache Jupiter quotes.

See `.planning/research/PITFALLS.md` for Drift account initialization, Alpaca paper/live confusion, and agent response parsing fragility.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Stabilize and Restructure
**Rationale:** Three critical bugs exist in the current codebase. Shipping new features on a broken foundation multiplies the bugs. Architecture restructuring without behavior change must happen before adding any new team, otherwise team_id scoping becomes a painful retrofit.
**Delivers:** Bug-free single quant team running through the new abstraction layer; `team_id` foundation in DB; YAML-driven TeamRegistry; parameterized TeamOrchestrator; no hanging analysis
**Addresses:** Team Registry, Per-Team Orchestration, Per-Team Portfolio Tracking (foundation only)
**Avoids:** Hanging analysis bug, global state race condition, plaintext password storage, shared PortfolioState singleton

### Phase 2: Crypto Team (Paper)
**Rationale:** Crypto price feeds and paper execution are independent of broker integration — they can be built and validated before touching live execution. CryptoMarketData and SolanaExecutor (paper mode) exercise the router abstractions built in Phase 1.
**Delivers:** Crypto DeFi team fully operational in paper mode; Jupiter price feeds; ccxt OHLCV data; SolanaExecutor simulating trades; team dashboard showing both teams
**Uses:** ccxt, httpx (Jupiter Price API), CryptoMarketData router
**Implements:** MarketDataRouter (crypto branch), ExecutionRouter (PaperExecutor for crypto)

### Phase 3: Live Execution — Alpaca and Jupiter
**Rationale:** Paper execution must be proven before live. Alpaca (stocks) and Jupiter spot swaps (crypto) are the two simplest live execution paths — REST APIs, no margin/liquidation complexity. Both can be wired in parallel since they use separate executor implementations.
**Delivers:** Quant stocks team executing real trades via Alpaca; Crypto DeFi team executing real Jupiter swaps; live/paper toggle per team; UI "LIVE" indicator
**Uses:** alpaca-py, solders, solana, base58, Jupiter v6 REST API
**Implements:** AlpacaExecutor, SolanaExecutor (live), server-side keypair management
**Avoids:** Solana transaction finality trap, Jupiter stale quote trap, Alpaca paper/live URL confusion

### Phase 4: Drift Perpetuals
**Rationale:** Drift requires a working SolanaExecutor and confirmed keypair/account setup. The `initialize_user()` requirement makes this a distinct phase — Drift account initialization is a known first-trade failure mode that needs dedicated setup and testing.
**Delivers:** Crypto team gains leverage and short positions via Drift perpetuals; funding rate analysis in agent context
**Uses:** driftpy
**Avoids:** Drift account initialization trap (initialize_user check on startup)

### Phase 5: Options Team
**Rationale:** Options analysis (Greeks, strategy recognition) requires dedicated agents that don't exist yet. Options data feed is a separate MarketDataRouter branch. This is the most complex domain — deferred until execution infrastructure is proven across simpler asset classes.
**Delivers:** Options team with Greeks-aware agents; options chains data feed; Alpaca options execution
**Uses:** Alpaca options order types; options-specific agent system prompts
**Implements:** OptionsMarketData router branch

### Phase 6: Cross-Team Risk and Analytics
**Rationale:** Cross-team risk management and performance analytics require multiple teams to be operational. This cannot be built until phases 1-3 are complete and producing data.
**Delivers:** Global exposure limits; correlation detection across teams; per-team Sharpe/drawdown/win rate; agent contribution tracking
**Addresses:** Cross-Team Risk Management, Team Performance Analytics (differentiators from FEATURES.md)

### Phase Ordering Rationale

- Phase 1 must come first: existing bugs will corrupt multi-team state if not fixed; `team_id` scoping is a database migration that gets harder the more data exists
- Phase 2 before Phase 3: paper execution validates the router abstractions before real money is involved; crypto paper is lower stakes than live
- Phase 3 groups Alpaca and Jupiter: both are straightforward REST execution paths that share the same "paper first, then live" pattern
- Phase 4 after Phase 3: Drift account initialization depends on a working SolanaExecutor with confirmed keypair
- Phase 5 last among execution phases: options is the most complex domain; existing infrastructure must be solid first
- Phase 6 last: requires data from multiple operational teams

### Research Flags

Phases needing deeper research during planning:
- **Phase 3 (Live Execution):** Private key management security model needs an explicit decision before implementation. Alpaca paper endpoint URL and order type support should be verified against current docs.
- **Phase 4 (Drift):** driftpy SDK capabilities need direct verification against docs.drift.trade before implementation. Drift account structure and margin management have limited training data coverage.
- **Phase 5 (Options):** Options data feed source is not resolved in research — broker options chain API specifics unknown.

Phases with standard patterns (can skip research-phase):
- **Phase 1 (Restructure):** Pure refactoring of existing codebase — no external API integration, well-understood patterns
- **Phase 2 (Crypto Paper):** ccxt and Jupiter Price API are well-documented REST integrations
- **Phase 6 (Analytics):** Standard financial metrics with no external dependencies

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Core stack (FastAPI, SQLAlchemy, anthropic) is HIGH. Solana packages (solders, driftpy) are MEDIUM — version numbers are approximate, verify on PyPI. Web search was unavailable during research. |
| Features | MEDIUM | Codebase-grounded claims (team_id scoping, orchestrator parameterization) are HIGH. DeFi-specific feature specs (Drift margin management) are LOW. |
| Architecture | HIGH | Router pattern, TeamRegistry, and PortfolioManager scoping are straightforward OOP — high confidence. SQLite WAL mode recommendation is standard. |
| Pitfalls | HIGH | Existing bugs (hang, race condition, plaintext passwords) are confirmed from codebase inspection. Solana pitfalls are well-documented in training data. |

**Overall confidence:** MEDIUM

### Gaps to Address

- **Private key security model:** How the server-side Solana keypair is stored and accessed needs an explicit decision before Phase 3 implementation. Options: environment variable (simplest), secrets manager (better for production), hardware key (overkill for single-user). This is a security-critical decision.
- **Drift SDK version verification:** driftpy >=0.7.0 is an approximate version — verify current release and changelog on PyPI and docs.drift.trade before Phase 4 begins.
- **Alpaca endpoint URLs:** Paper vs live base URLs may have changed. Verify current paper trading endpoint before Phase 3 implementation.
- **Options data feed:** No concrete source identified for options chains data. Needs research before Phase 5 planning begins.
- **yfinance rate limiting:** With multiple stock-focused teams, shared caching of market data fetches will be needed. TTL cache implementation is straightforward but needs to be explicitly planned in Phase 1 or Phase 2.

## Sources

### Primary (HIGH confidence)
- Codebase inspection (trading/) — existing stack, bug identification, current architecture
- Anthropic SDK docs (training data) — AsyncAnthropic, wait_for patterns
- Jupiter v6 REST API docs (training data) — quote/swap flow

### Secondary (MEDIUM confidence)
- solders, solana-py, driftpy PyPI/GitHub (training data) — Solana execution stack
- alpaca-py docs (training data) — paper/live flag, TradingClient interface
- ccxt docs (training data) — unified exchange API
- Drift Protocol docs (training data) — initialize_user requirement, account structure

### Tertiary (LOW confidence)
- Drift margin/liquidation specifics — needs doc.drift.trade verification before Phase 4
- Options data feed options — not researched; needs dedicated research before Phase 5

---
*Research completed: 2026-03-25*
*Ready for roadmap: yes*

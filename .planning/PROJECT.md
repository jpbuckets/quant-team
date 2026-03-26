# Quant Team Trading Platform

## What This Is

An AI-powered multi-team investment platform where specialized teams of Claude agents analyze markets, produce trade recommendations, and execute trades. Currently a single "quant team" with Macro, Quant, Risk, and CIO agents running sequential round-table analysis on stocks via a FastAPI web dashboard. Evolving toward multiple independent teams (stocks, crypto, options, long-term) with real trade execution.

## Core Value

The AI agent round-table produces actionable trade decisions that can be automatically executed — analysis without execution is just noise.

## Requirements

### Validated

- ✓ Multi-agent orchestration (Macro → Quant → Risk → CIO pipeline) — existing
- ✓ Market data fetching via yfinance — existing
- ✓ Web dashboard with session history — existing
- ✓ Authentication system (cookie-based, bcrypt) — Phase 1
- ✓ SQLite persistence for sessions and recommendations — existing
- ✓ Scheduled autonomous sessions (APScheduler) — existing
- ✓ Async analysis pipeline with 5-min timeouts — Phase 1
- ✓ Per-session state isolation (no race conditions) — Phase 1
- ✓ Bcrypt password hashing — Phase 1
- ✓ YAML-backed team registry with dynamic agent construction — Phase 1
- ✓ team_id scoping on all DB models — Phase 1

### Active

- [ ] Multi-team architecture — independent teams with specialized agents per investment domain
- [ ] Crypto team — agents specialized in DeFi, on-chain analysis, Solana ecosystem
- [ ] Options team — agents specialized in Greeks, volatility, options strategies
- [ ] Long-term investing team — agents focused on fundamentals, value investing
- [ ] Crypto trade execution via Solana (Phantom Wallet API, Drift Protocol, Jupiter)
- [ ] Stock trade execution via broker API (TBD — Alpaca, IBKR, or other)
- [ ] Team-specific dashboards and portfolio tracking

### Out of Scope

- Mobile app — web-first
- Social/sharing features — this is a personal trading tool
- Backtesting engine — focus on live analysis and execution first
- Multi-user support — single user for now

## Context

- **Existing codebase:** Brownfield Python project with FastAPI, Claude agents, yfinance, SQLite
- **Analysis bug fixed:** Async pipeline with 5-min timeouts, per-session state isolation (Phase 1 complete).
- **Crypto execution:** Solana ecosystem chosen — Phantom Wallet API for wallet management, Drift Protocol for perpetuals/lending, Jupiter for spot swaps. These have well-documented APIs.
- **Stock execution:** Broker not yet chosen. Alpaca (simpler API, commission-free) and IBKR (broader access) are candidates.
- **Team architecture complete:** YAML-backed TeamRegistry with dynamic agent construction. New teams added via config files, no Python changes needed (Phase 1 complete).

## Constraints

- **Tech stack**: Python/FastAPI — keep existing stack, extend don't rewrite
- **AI provider**: Anthropic Claude — all agents use Claude API
- **Database**: SQLite for now — sufficient for single-user
- **Crypto chain**: Solana — Phantom/Drift/Jupiter ecosystem

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fix analysis bug before new features | Can't build on a broken foundation | — Pending |
| Solana for crypto execution | Phantom/Drift/Jupiter have good APIs, user preference | — Pending |
| Stock broker TBD | Need to evaluate Alpaca vs IBKR vs others | — Pending |
| Keep SQLite | Single user, no need for Postgres complexity yet | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-26 after Phase 1 completion*

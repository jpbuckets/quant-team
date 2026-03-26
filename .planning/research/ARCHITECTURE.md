# Architecture Research: AI Multi-Team Trading Platform

**Researched:** 2026-03-25
**Focus:** Evolving single-team to multi-team architecture

## Current Architecture Problems

What's hardwired in `TradingDesk` and must change:

1. **4 hardcoded agent imports** — Macro, Quant, Risk, CIO agents imported directly
2. **Singleton PortfolioState** — `PortfolioState(id=1)` means one portfolio for everything
3. **Schema columns tied to quant team** — AgentSession columns assume macro/quant/risk/cio structure
4. **Stock-only market data** — yfinance only, no crypto or options data
5. **PDT-only risk checks** — Pattern Day Trader rules don't apply to crypto

## Target Architecture: 8 Components

### 1. TeamRegistry
- YAML-backed config store
- Owns `TeamConfig` + `AgentSpec` dataclasses
- Each team defines: name, asset_class, agents[], risk_limits, schedule_cron, execution_backend
- No database needed — config files loaded at startup

### 2. TeamOrchestrator (replaces TradingDesk)
- Receives `TeamConfig`, constructs agents dynamically from config
- Delegates all asset-class-specific work to routers
- Same round-table pattern, but agents come from config not imports
- One instance per team per session

### 3. MarketDataRouter
- Routes to appropriate data source based on `config.asset_class`
- `StockMarketData` — existing yfinance wrapper
- `CryptoMarketData` — new, backed by ccxt + Jupiter price API
- `OptionsMarketData` — future, broker options chain API
- Returns normalized `MarketSnapshot` regardless of source

### 4. ExecutionRouter
- Routes to appropriate executor based on team config
- `PaperExecutor` — extracted from current code, simulates trades
- `AlpacaExecutor` — Alpaca API for stock trades
- `SolanaExecutor` — Jupiter/Drift for crypto trades
- Returns normalized `ExecutionResult`

### 5. PortfolioManager (evolved)
- Gains `team_id` filtering on all queries
- Singleton row becomes one row per team
- Same interface, scoped by team

### 6. RiskChecker (evolved)
- No structural change needed
- `TeamConfig.risk_limits` supplies per-team limits
- PDT checker only runs for stock teams

### 7. Scheduler (evolved)
- Iterates registry on startup
- Registers cron jobs per team from `config.schedule_cron`
- Crypto teams can run 24/7, stock teams during market hours

### 8. API Layer (evolved)
- URL structure: `/api/teams/{team_id}/sessions`, `/api/teams/{team_id}/portfolio`
- Team selector in dashboard replaces single-team view
- Cross-team summary endpoint for aggregate view

## Data Flow (Multi-Team)

```
TeamRegistry
    │
    ├── Team: "Quant Stocks"
    │     │
    │     TeamOrchestrator
    │     ├── MacroAgent → QuantAgent → RiskAgent → CIOAgent
    │     ├── MarketDataRouter → StockMarketData (yfinance)
    │     ├── RiskChecker (PDT + position limits)
    │     └── ExecutionRouter → AlpacaExecutor
    │
    ├── Team: "Crypto DeFi"
    │     │
    │     TeamOrchestrator
    │     ├── OnChainAgent → DeFiAgent → RiskAgent → CIOAgent
    │     ├── MarketDataRouter → CryptoMarketData (ccxt + Jupiter)
    │     ├── RiskChecker (position limits only)
    │     └── ExecutionRouter → SolanaExecutor (Jupiter + Drift)
    │
    └── Team: "Options"
          │
          TeamOrchestrator
          ├── VolAgent → GreeksAgent → RiskAgent → CIOAgent
          ├── MarketDataRouter → OptionsMarketData
          ├── RiskChecker (Greeks limits + position limits)
          └── ExecutionRouter → AlpacaExecutor (options)
```

## Build Order (4 Stages)

### Stage 1: Restructure (no new features)
Make existing quant team work through new abstractions. Extract TeamConfig, TeamOrchestrator, TeamRegistry. Existing tests (none) can't break because none exist — but the app must still work identically.

### Stage 2: Crypto Team
Add CryptoMarketData (ccxt + Jupiter prices). Create crypto team config with DeFi-focused agents. Paper execution first.

### Stage 3: Live Execution
Wire Alpaca for stock trading (paper → live). Wire Solana for crypto execution (Jupiter swaps → Drift perpetuals).

### Stage 4: Options + Long-Term Teams
Add options-specific agents and data. Add long-term investing team with fundamentals focus.

## Anti-Patterns to Avoid

1. **Branching on asset class inside orchestrator** — collapses the abstraction; use routers instead
2. **Hardcoded AgentSession columns per agent role** — use JSON blob for agent responses, not per-agent columns
3. **Singleton PortfolioState** — must be scoped by team_id from day one
4. **yfinance for crypto data** — insufficient for on-chain Solana context
5. **Building live execution before paper execution is proven** — always paper first

## SQLite Concurrency

Enable WAL mode before concurrent team sessions:
```python
engine = create_engine("sqlite:///data/dashboard.db", connect_args={"check_same_thread": False})
with engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL"))
```

---
*Architecture research: 2026-03-25*

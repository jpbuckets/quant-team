# Requirements: Quant Team Trading Platform

**Defined:** 2026-03-25
**Core Value:** The AI agent round-table produces actionable trade decisions that can be automatically executed

## v1 Requirements

Requirements for initial milestone. Each maps to roadmap phases.

### Stability

- [ ] **STAB-01**: Analysis button completes within 5 minutes or surfaces a timeout error (no infinite hang)
- [ ] **STAB-02**: Multiple simultaneous sessions don't corrupt each other's state or trigger duplicate trades
- [ ] **STAB-03**: User passwords are hashed with bcrypt, never stored or compared in plaintext
- [ ] **STAB-04**: Analysis progress is visible to the user during a running session

### Multi-Team Architecture

- [ ] **TEAM-01**: Teams are defined via configuration files with name, asset class, agent specs, risk limits, and schedule
- [ ] **TEAM-02**: All database models (PortfolioState, PortfolioPosition, TradeRecord, AgentSession, Recommendation) are scoped by team_id
- [ ] **TEAM-03**: Orchestrator accepts team configuration and constructs agents dynamically (no hardcoded agent imports)
- [ ] **TEAM-04**: Each team can have a different set of specialized agents with team-specific system prompts
- [ ] **TEAM-05**: Teams can be scheduled independently (crypto 24/7, stocks market hours only)

### Market Data

- [ ] **DATA-01**: Crypto team can fetch Solana token prices via Jupiter Price API
- [ ] **DATA-02**: Crypto team can fetch CEX market data (OHLCV, tickers) via ccxt
- [ ] **DATA-03**: Stock team can fetch equity market data via yfinance (existing, must continue working)
- [ ] **DATA-04**: Market data is routed to the correct source based on team's asset class

### Trade Execution

- [ ] **EXEC-01**: All teams start in paper trading mode by default
- [ ] **EXEC-02**: Paper trades are logged with what would have happened (symbol, side, quantity, price)
- [ ] **EXEC-03**: Live vs paper mode is toggleable per team
- [ ] **EXEC-04**: Execution is routed to the correct backend based on team configuration

### Dashboard & UI

- [ ] **DASH-01**: User can select between teams from the main dashboard
- [ ] **DASH-02**: Each team has its own portfolio view showing positions, P&L, and session history
- [ ] **DASH-03**: Cross-team summary view shows aggregate portfolio across all teams
- [ ] **DASH-04**: UI clearly indicates whether a team is in paper or live mode

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Live Execution

- **LIVE-01**: Crypto team can execute spot swaps on Solana via Jupiter API
- **LIVE-02**: Stock team can execute trades via Alpaca API
- **LIVE-03**: Crypto team can trade perpetuals via Drift Protocol
- **LIVE-04**: Server-side Solana keypair management for autonomous crypto trading

### Options Team

- **OPTS-01**: Options-specialized agents with Greeks analysis
- **OPTS-02**: Options chain data feed from broker API
- **OPTS-03**: Options execution via Alpaca

### Analytics

- **ANLT-01**: Per-team performance metrics (Sharpe ratio, drawdown, win rate)
- **ANLT-02**: Agent contribution tracking (which agent's recommendations performed best)
- **ANLT-03**: Historical performance comparison between teams

## Out of Scope

| Feature | Reason |
|---------|--------|
| Backtesting engine | Massive complexity, not stated need |
| Multi-user auth | Single user tool |
| Multi-chain crypto | Solana only — adding Ethereum/BSC adds huge complexity |
| Streaming WebSockets | Polling sufficient for analysis cadence (not HFT) |
| Mobile app | Web-first |
| Social/copy trading | Personal trading tool |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| STAB-01 | TBD | Pending |
| STAB-02 | TBD | Pending |
| STAB-03 | TBD | Pending |
| STAB-04 | TBD | Pending |
| TEAM-01 | TBD | Pending |
| TEAM-02 | TBD | Pending |
| TEAM-03 | TBD | Pending |
| TEAM-04 | TBD | Pending |
| TEAM-05 | TBD | Pending |
| DATA-01 | TBD | Pending |
| DATA-02 | TBD | Pending |
| DATA-03 | TBD | Pending |
| DATA-04 | TBD | Pending |
| EXEC-01 | TBD | Pending |
| EXEC-02 | TBD | Pending |
| EXEC-03 | TBD | Pending |
| EXEC-04 | TBD | Pending |
| DASH-01 | TBD | Pending |
| DASH-02 | TBD | Pending |
| DASH-03 | TBD | Pending |
| DASH-04 | TBD | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 0
- Unmapped: 21

---
*Requirements defined: 2026-03-25*
*Last updated: 2026-03-25 after initial definition*

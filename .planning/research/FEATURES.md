# Features Research: AI Multi-Team Trading Platform

**Researched:** 2026-03-25
**Confidence:** MEDIUM overall (HIGH for codebase-grounded claims, MEDIUM/LOW for DeFi API specifics)

## Table Stakes

These are required for a functional multi-team trading platform. Without them, the system doesn't work.

### Team Registry & Scoping
- **Team data model** — `team_id` on all existing models (PortfolioState, PortfolioPosition, TradeRecord, AgentSession, Recommendation)
- **Team configuration** — per-team agent definitions, system prompts, asset universe, risk parameters
- **Team isolation** — teams don't see or affect each other's portfolios or sessions
- **Complexity:** HIGH — touches every existing model and query
- **Dependencies:** None — this is the foundation everything else builds on

### Per-Team Orchestration
- **Parameterized TradingDesk** — current orchestrator hardcodes 4 agents; needs to accept team config
- **Team-specific agent pipelines** — crypto team has different agents than options team
- **Per-team scheduling** — different teams may run at different times (crypto 24/7, stocks market hours)
- **Complexity:** MEDIUM — existing orchestrator is well-structured, needs parameterization not rewrite
- **Dependencies:** Team Registry

### Per-Team Portfolio Tracking
- **Separate portfolio per team** — positions, P&L, allocation tracked independently
- **Team dashboard** — view each team's performance, sessions, recommendations
- **Cross-team summary** — aggregate view across all teams
- **Complexity:** MEDIUM
- **Dependencies:** Team Registry

### Paper Trading Mode
- **Simulated execution** — all new teams start in paper mode
- **Live/paper toggle** — explicit switch per team, not global
- **Paper trade logging** — track what would have happened for verification
- **Complexity:** LOW-MEDIUM
- **Dependencies:** Team Registry, Execution layer

### Crypto Price Feeds
- **Solana token prices** — yfinance doesn't reliably cover Solana tokens
- **Jupiter Price API or CoinGecko** — needed before crypto agents can analyze
- **Real-time vs polling** — polling is sufficient for analysis cadence
- **Complexity:** LOW
- **Dependencies:** None — can be built independently

### Basic Crypto Execution (Jupiter Spot)
- **Jupiter swap API** — spot token swaps on Solana
- **Wallet management** — server-side keypair for autonomous trading (security-critical)
- **Transaction confirmation** — verify swaps landed on-chain
- **Complexity:** MEDIUM-HIGH
- **Dependencies:** Crypto Price Feeds, Paper Trading Mode

### Stock Broker Integration
- **Alpaca or IBKR API** — place market/limit orders for stocks
- **Position sync** — reconcile broker positions with internal tracking
- **Order status tracking** — pending, filled, rejected states
- **Complexity:** MEDIUM (Alpaca is simpler than IBKR)
- **Dependencies:** Paper Trading Mode

## Differentiators

These add value but aren't required for the system to function.

### Drift Protocol Integration
- **Perpetual futures on Solana** — leverage, short positions
- **Funding rate analysis** — agents can factor in funding costs
- **Margin management** — track margin requirements, liquidation levels
- **Complexity:** HIGH — margin accounts, funding rates, liquidation logic
- **Dependencies:** Jupiter Spot working first

### Cross-Team Risk Management
- **Global exposure limits** — total portfolio risk across all teams
- **Correlation detection** — warn when multiple teams take correlated positions
- **Capital allocation** — how much capital each team gets to deploy
- **Complexity:** MEDIUM-HIGH
- **Dependencies:** All teams operational

### Options-Specific Analysis
- **Greeks calculation** — Delta, Gamma, Theta, Vega per position
- **Strategy recognition** — identify spreads, straddles, condors
- **Expiration tracking** — alerts for approaching expirations
- **Complexity:** HIGH
- **Dependencies:** Options team agents, broker supporting options

### Team Performance Analytics
- **Sharpe ratio, drawdown, win rate** per team
- **Agent contribution tracking** — which agent's recommendations performed best
- **Historical comparison** — team performance over time
- **Complexity:** MEDIUM
- **Dependencies:** Multiple completed sessions per team

## Anti-Features (Do NOT Build)

| Feature | Why Not |
|---------|---------|
| Backtesting engine | Massive complexity, not stated need, distracts from live execution |
| Multi-user auth | Single user tool — existing auth is sufficient |
| Multi-chain crypto | Solana only — adding Ethereum/BSC/etc adds huge complexity |
| Streaming WebSockets | Polling is sufficient for analysis cadence (not HFT) |
| Options on crypto | Extremely niche, defer indefinitely |
| Social/copy trading | Out of scope per project definition |

## Suggested Build Order

1. Team registry + `team_id` scoped DB models (foundation)
2. Generic team orchestrator (parameterized TradingDesk)
3. Crypto price feeds (Jupiter/CoinGecko)
4. Jupiter spot swap execution (paper mode first)
5. Alpaca stock execution (paper mode first)
6. Team-specific UI/dashboards
7. Drift perpetuals (later phase)

## Open Questions

- **Drift SDK:** Capabilities need direct doc verification before implementation phase
- **Alpaca paper trading:** Confirm current paper endpoint URL and order type support
- **Phantom/keypair:** Server-side autonomous trading requires private key management — security model for key storage needs explicit decision before implementation

---
*Research: 2026-03-25*

# Stack Research: AI Multi-Team Trading Platform

**Researched:** 2026-03-25
**Existing base:** Python 3.12 / FastAPI / anthropic SDK / yfinance / SQLite / APScheduler

**Note:** Web search unavailable during research. Findings based on codebase inspection and training data (cutoff Aug 2025). Version pins are approximate — verify on PyPI before pinning.

## Existing Stack (Keep As-Is)

All validated and working — do not replace.

| Technology | Version | Role |
|------------|---------|------|
| Python | 3.12 | Runtime |
| FastAPI | >=0.110.0 | HTTP server + dashboard |
| SQLAlchemy | >=2.0.0 | ORM |
| SQLite | via aiosqlite | Persistence (keep for single user) |
| anthropic | >=0.40.0 | Claude API, agents |
| yfinance | >=0.2.30 | Stock market data |
| APScheduler | >=3.10.0 | Autonomous scheduling |

## New: Solana Execution Stack

### solders >=0.20.0 (MEDIUM confidence)
Low-level Solana primitives (keypairs, transactions, instructions). Rust/PyO3. Canonical primitive layer for Solana Python work; preferred over older solana-py types.

### solana >=0.33.0 (MEDIUM confidence)
Async Solana JSON-RPC client. Sending transactions, querying accounts, getting recent blockhash. Wraps all RPC methods with proper types.

### driftpy >=0.7.0 (MEDIUM confidence — verify against docs.drift.trade)
Drift Protocol's official Python SDK. Built on anchorpy. Typed methods for perp orders, positions, funding rates. Use instead of raw anchorpy — avoids hand-encoding Anchor discriminators.

### Jupiter v6 REST API via httpx (HIGH confidence)
Stable REST API at `https://quote-api.jup.ag/v6`. Use `GET /quote` then `POST /swap` to get serialized swap transaction, sign with solders, send via solana-py. No dedicated Python SDK needed — third-party wrappers lag behind API changes.

### base58 >=2.1.0 (HIGH confidence)
Encode/decode keypairs from environment variables. Tiny, stable.

### Critical Phantom Note
**Phantom is a browser extension. There is no server-side Phantom API.** For server-side execution, load a keypair from an environment variable (base58-encoded private key) and sign transactions directly with solders. "Phantom Wallet API" means using a keypair originally created in Phantom — not the browser extension itself.

## New: Stock Broker Execution

### Recommendation: Alpaca, not IBKR (HIGH confidence on tradeoff)

IBKR requires TWS or IB Gateway running as a local daemon — hard deployment blocker for Docker. Requires persistent desktop environment or VNC. Not worth the complexity.

Alpaca is pure REST/WebSocket with API key auth. Drop-in HTTP integration.

### alpaca-py >=0.26.0 (MEDIUM confidence — verify on PyPI)
Official Alpaca Python SDK. Key classes: `TradingClient` (orders, positions), `StockHistoricalDataClient`. Paper trading is first-class: same SDK, `paper=True` flag.

## New: Crypto Market Data

### ccxt >=4.3.0 (MEDIUM confidence)
Unified exchange API for crypto OHLCV, tickers, order books across 100+ exchanges. Use for CEX-side price data to give crypto team market context.

For on-chain Solana token prices, use Jupiter's price API (`https://price.jup.ag/v6/price`) via httpx — more accurate for DeFi tokens.

## Multi-Agent Orchestration: No New Framework

**Do NOT adopt LangChain, LangGraph, or CrewAI.**

The existing `Agent` class pattern (plain Python calling Anthropic SDK directly) is simple, debuggable, and correct. LangChain/LangGraph add substantial complexity and fight the fine-grained control needed.

Right move: extract `TeamConfig` dataclass + `TeamRegistry` dict + generalized `TeamOrchestrator` from existing `TradingDesk`. Multi-team via configuration, not framework adoption.

For future parallel team execution: use `asyncio` + `AsyncAnthropic` (already in anthropic package).

## Analysis Hang Fix (No New Packages)

Root cause: `anthropic.Anthropic()` (sync client) makes blocking HTTP calls with no timeout. FastAPI route calls `TradingDesk.run_trading_session()` synchronously on the event loop.

Fix: `asyncio.wait_for()` + `loop.run_in_executor()` with 300-second timeout. Uses stdlib only.

## New Packages Summary

```toml
"solders>=0.20.0",
"solana>=0.33.0",
"driftpy>=0.7.0",
"base58>=2.1.0",
"alpaca-py>=0.26.0",
"ccxt>=4.3.0",
```

---
*Stack research: 2026-03-25*

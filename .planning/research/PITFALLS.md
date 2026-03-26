# Pitfalls Research: AI Multi-Team Trading Platform

**Researched:** 2026-03-25
**Focus:** Common mistakes in AI trading platforms, DeFi integration, broker APIs

## Critical Pitfalls

### 1. Hanging Analysis Button (EXISTING BUG)
**What:** `Agent.analyze()` uses synchronous `anthropic.Anthropic()` client inside FastAPI. No timeout on `messages.create()` calls. If Claude API is slow or stalls, the request hangs forever.

**Warning signs:** UI spinner never stops, no error in logs, no timeout
**Root cause:** Sync HTTP client blocking the async event loop

**Prevention:**
- Switch to `AsyncAnthropic` client
- Use `asyncio.create_task()` for background analysis
- Add `asyncio.wait_for()` with 300-second timeout per agent call
- Surface progress to UI via SSE or polling endpoint

**Phase:** Phase 1 (fix before anything else)

### 2. Global State Race Condition
**What:** `_generating`, `_progress`, and `_last_error` are module-level globals in the API. Multiple simultaneous requests (or scheduled + manual sessions) will stomp on each other's state.

**Warning signs:** Duplicate trade executions, garbled progress messages, SQLite write conflicts
**Prevention:**
- Move session state into a per-session object (keyed by session ID)
- Use database for state that must survive restarts
- Enable SQLite WAL mode for concurrent writes

**Phase:** Phase 1 (must fix alongside hang bug)

### 3. Plaintext Password Storage
**What:** `ALLOWED_USERS` env var stores passwords verbatim, compared directly in `authenticate()`. The HMAC comparison prevents timing attacks but passwords aren't hashed.

**Warning signs:** Any `.env` file leak exposes all credentials
**Prevention:**
- Hash passwords with bcrypt before storage
- Must fix before adding broker API keys to the system

**Phase:** Phase 1 (security baseline)

### 4. Solana Transaction Finality
**What:** Using `processed` commitment level instead of `confirmed` causes ghost positions — transactions appear confirmed but can roll back.

**Warning signs:** Portfolio shows positions that don't exist on-chain
**Prevention:**
- Always use `confirmed` or `finalized` commitment
- After sending transaction, poll for confirmation before updating local state
- Implement transaction retry with nonce management

**Phase:** Crypto execution phase

### 5. Phantom Wallet is Browser-Only
**What:** Phantom is a browser extension wallet. There is no server-side Phantom API. Cannot sign transactions from Python.

**Warning signs:** Searching for `phantom-py` or `phantom-sdk` — they don't exist
**Prevention:**
- Use `solders` Keypair for server-side signing
- Load private key from environment variable (base58-encoded)
- Store keypair securely (never in code, never in git)

**Phase:** Crypto execution phase

### 6. Jupiter Stale Quotes
**What:** Jupiter quote fetched during analysis time is NOT the execution price. Quotes expire quickly. Using a stale quote results in failed or unfavorable swaps.

**Warning signs:** Swap transactions fail with "quote expired" or slippage errors
**Prevention:**
- Fetch fresh quote immediately before building swap transaction (within seconds)
- Set appropriate slippage tolerance (0.5-1% for liquid pairs, higher for illiquid)
- Never cache Jupiter quotes

**Phase:** Crypto execution phase

### 7. Drift Account Initialization
**What:** Drift requires `initialize_user()` to be called before any trading can happen. The SDK doesn't do this automatically. First trade will fail silently or with cryptic error.

**Warning signs:** First Drift trade fails with account-not-found error
**Prevention:**
- Check if user account exists on startup
- Call `initialize_user()` if not
- Document this in setup instructions

**Phase:** Drift integration phase (after Jupiter spot)

### 8. Multi-Team Shared Portfolio Row
**What:** Current `PortfolioState` uses `id=1` singleton. When multiple teams run concurrently, they'll all read/write the same row, causing race conditions and incorrect portfolio accounting.

**Warning signs:** Team A's trades appear in Team B's portfolio, balance calculations wrong
**Prevention:**
- Add `team_id` column to PortfolioState, PortfolioPosition, TradeRecord
- Scope ALL portfolio queries by team_id from day one
- Never use a singleton portfolio row

**Phase:** Multi-team architecture phase (before second team is added)

## Medium Pitfalls

### 9. Alpaca Paper vs Live Confusion
**What:** Alpaca paper and live use different base URLs. Easy to accidentally trade real money during testing.

**Prevention:**
- Default to paper mode, require explicit flag for live
- Different API keys for paper vs live
- Visual indicator in UI (big red "LIVE" banner)

### 10. Agent Response Parsing Fragility
**What:** CIO agent outputs JSON trade decisions. If the response format drifts (Claude models change behavior between versions), parsing breaks silently.

**Prevention:**
- Strict JSON schema validation on CIO output
- Fallback to "no trade" if parsing fails (never guess)
- Log raw agent responses for debugging

### 11. yfinance Rate Limiting
**What:** yfinance scrapes Yahoo Finance and gets rate-limited under heavy use. Multiple teams hitting it simultaneously will trigger blocks.

**Prevention:**
- Cache market data per symbol with TTL (5-15 min for analysis cadence)
- Use a single shared data fetcher, not per-team fetches
- Consider paid data source if rate limits become a blocker

---
*Pitfalls research: 2026-03-25*

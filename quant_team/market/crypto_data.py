"""Crypto market data provider using Jupiter Price API v3 and ccxt."""

from __future__ import annotations

import logging
import os
import time

import ccxt
import httpx
import pandas as pd

logger = logging.getLogger("quant_team")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JUPITER_PRICE_URL = "https://api.jup.ag/price/v3/price"

KNOWN_MINTS: dict[str, str] = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def ticker_to_mint(symbol: str) -> str | None:
    """Return the Solana mint address for a known token symbol, or None."""
    return KNOWN_MINTS.get(symbol.upper())


def ticker_to_ccxt_pair(symbol: str, quote: str = "USDT") -> str:
    """Convert a token symbol to a ccxt trading pair (e.g. 'SOL' -> 'SOL/USDT')."""
    return f"{symbol.upper()}/{quote}"


def fetch_jupiter_prices(mints: list[str]) -> dict[str, float]:
    """Fetch USD prices for given mint addresses from Jupiter Price API v3.

    Returns a dict mapping mint address to float price.
    Returns {} on any failure (graceful degradation).
    """
    api_key = os.environ.get("JUPITER_API_KEY", "")
    if not api_key:
        logger.warning("JUPITER_API_KEY is not set — Jupiter price fetches will be skipped")
    ids = ",".join(mints)
    try:
        resp = httpx.get(
            JUPITER_PRICE_URL,
            params={"ids": ids},
            headers={"X-API-Key": api_key},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return {mint: float(entry["price"]) for mint, entry in data.items() if entry}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# CryptoMarketData
# ---------------------------------------------------------------------------

_PERIOD_TO_LIMIT: dict[str, int] = {
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
}

_INTERVAL_TO_TF: dict[str, str] = {
    "1d": "1d",
    "1h": "1h",
    "5m": "5m",
}


class CryptoMarketData:
    """Fetches crypto market data via ccxt (CEX) and Jupiter Price API (Solana DeFi)."""

    def __init__(self, exchange_name: str = "binance", cache_ttl: int = 60):
        self.exchange = getattr(ccxt, exchange_name)()
        self.cache_ttl = cache_ttl
        self._quote_cache: dict[str, tuple[float, dict]] = {}
        self._ohlcv_cache: dict[str, tuple[float, pd.DataFrame]] = {}

    def fetch_ohlcv(
        self, ticker: str, period: str = "3mo", interval: str = "1d"
    ) -> pd.DataFrame:
        """Fetch OHLCV candlestick data for a token via ccxt.

        Returns a DataFrame with columns [open, high, low, close, volume]
        and a DatetimeIndex, compatible with compute_all() from indicators.py.
        """
        cache_key = f"{ticker}_{period}_{interval}"
        now = time.time()
        if cache_key in self._ohlcv_cache:
            ts, df = self._ohlcv_cache[cache_key]
            if now - ts < self.cache_ttl:
                return df

        limit = _PERIOD_TO_LIMIT.get(period, 90)
        tf = _INTERVAL_TO_TF.get(interval, "1d")
        try:
            raw = self.exchange.fetch_ohlcv(ticker_to_ccxt_pair(ticker), timeframe=tf, limit=limit)
            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            self._ohlcv_cache[cache_key] = (now, df)
            return df
        except Exception as e:
            raise ValueError(f"No OHLCV data for {ticker}: {e}") from e

    def fetch_quote(self, ticker: str) -> dict:
        """Fetch current price quote for a token.

        Tries Jupiter Price API first (for accurate Solana on-chain pricing),
        then falls back to ccxt ticker. Returns gracefully on failure.
        """
        now = time.time()
        if ticker in self._quote_cache:
            ts, data = self._quote_cache[ticker]
            if now - ts < self.cache_ttl:
                return data

        # Default/empty quote structure
        quote: dict = {
            "ticker": ticker,
            "price": 0.0,
            "previous_close": 0.0,
            "open": 0.0,
            "day_high": 0.0,
            "day_low": 0.0,
            "volume": 0,
            "market_cap": 0.0,
            "change_pct": 0.0,
        }

        try:
            # Try Jupiter first
            mint = ticker_to_mint(ticker)
            if mint:
                prices = fetch_jupiter_prices([mint])
                if prices.get(mint):
                    quote["price"] = prices[mint]
                    self._quote_cache[ticker] = (now, quote)
                    return quote

            # Fallback to ccxt
            raw = self.exchange.fetch_ticker(ticker_to_ccxt_pair(ticker))
            quote["price"] = float(raw.get("last") or 0.0)
            quote["volume"] = int(raw.get("quoteVolume") or 0)
        except Exception:
            pass

        self._quote_cache[ticker] = (now, quote)
        return quote

    def fetch_multiple_quotes(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch quotes for multiple tokens."""
        results = {}
        for ticker in tickers:
            try:
                results[ticker] = self.fetch_quote(ticker)
            except Exception:
                pass
        return results

    def fetch_options_chain(self, ticker: str) -> dict:
        """Return empty options structure — crypto assets have no options chains in Phase 2."""
        return {"ticker": ticker, "expirations": [], "chains": {}}

    def get_market_summary(self, tickers: list[str]) -> str:
        """Formatted text summary of crypto market data for agent consumption."""
        lines = ["# Crypto Market Summary", ""]
        lines.append("## Token Prices")
        for ticker in tickers:
            try:
                q = self.fetch_quote(ticker)
                price = q["price"]
                volume = q["volume"]
                lines.append(
                    f"- **{ticker}**: ${price:,.4f} | Vol: {volume:,}"
                )
            except Exception:
                lines.append(f"- **{ticker}**: unavailable")
        return "\n".join(lines)

    def get_options_summary(self, ticker: str) -> str:
        """Return empty string — crypto has no options chains."""
        return ""

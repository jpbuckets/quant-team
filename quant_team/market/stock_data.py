"""Stock market data provider using yfinance."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


class StockMarketData:
    """Fetches stock market data via yfinance with caching."""

    def __init__(self, cache_ttl: int = 60):
        self.cache_ttl = cache_ttl
        self._quote_cache: dict[str, tuple[float, dict]] = {}
        self._ohlcv_cache: dict[str, tuple[float, pd.DataFrame]] = {}

    def fetch_ohlcv(
        self, ticker: str, period: str = "3mo", interval: str = "1d"
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a ticker."""
        cache_key = f"{ticker}_{period}_{interval}"
        now = time.time()
        if cache_key in self._ohlcv_cache:
            ts, df = self._ohlcv_cache[cache_key]
            if now - ts < self.cache_ttl:
                return df

        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval)
        if df.empty:
            raise ValueError(f"No OHLCV data for {ticker}")

        df.columns = [c.lower() for c in df.columns]
        # Ensure standard column names
        col_map = {"stock splits": "stock_splits"}
        df.rename(columns=col_map, inplace=True)

        self._ohlcv_cache[cache_key] = (now, df)
        return df

    def fetch_quote(self, ticker: str) -> dict:
        """Fetch current quote for a ticker."""
        now = time.time()
        if ticker in self._quote_cache:
            ts, data = self._quote_cache[ticker]
            if now - ts < self.cache_ttl:
                return data

        t = yf.Ticker(ticker)
        info = t.fast_info
        quote = {
            "ticker": ticker,
            "price": float(info.last_price) if info.last_price else 0.0,
            "previous_close": float(info.previous_close) if info.previous_close else 0.0,
            "open": float(info.open) if info.open else 0.0,
            "day_high": float(info.day_high) if info.day_high else 0.0,
            "day_low": float(info.day_low) if info.day_low else 0.0,
            "volume": int(info.last_volume) if info.last_volume else 0,
            "market_cap": float(info.market_cap) if info.market_cap else 0.0,
        }
        if quote["previous_close"] > 0:
            quote["change_pct"] = (quote["price"] / quote["previous_close"] - 1) * 100
        else:
            quote["change_pct"] = 0.0

        self._quote_cache[ticker] = (now, quote)
        return quote

    def fetch_multiple_quotes(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch quotes for multiple tickers."""
        results = {}
        for ticker in tickers:
            try:
                results[ticker] = self.fetch_quote(ticker)
            except Exception:
                pass
        return results

    def fetch_options_chain(self, ticker: str) -> dict:
        """Fetch options chain for a ticker."""
        t = yf.Ticker(ticker)
        expirations = t.options
        if not expirations:
            return {"ticker": ticker, "expirations": [], "chains": {}}

        chains = {}
        # Fetch first 3 expirations to avoid too much data
        for exp in expirations[:3]:
            try:
                chain = t.option_chain(exp)
                calls = chain.calls[
                    ["strike", "lastPrice", "bid", "ask", "volume",
                     "openInterest", "impliedVolatility", "inTheMoney"]
                ].to_dict("records")
                puts = chain.puts[
                    ["strike", "lastPrice", "bid", "ask", "volume",
                     "openInterest", "impliedVolatility", "inTheMoney"]
                ].to_dict("records")
                chains[exp] = {"calls": calls, "puts": puts}
            except Exception:
                continue

        return {"ticker": ticker, "expirations": list(expirations), "chains": chains}

    def get_market_summary(self, tickers: list[str]) -> str:
        """Formatted text summary for agent consumption."""
        lines = ["# Market Summary", ""]

        # Market indices
        indices = {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "Russell 2000", "DIA": "Dow Jones"}
        lines.append("## Market Indices")
        for sym, name in indices.items():
            try:
                q = self.fetch_quote(sym)
                lines.append(
                    f"- **{name}** ({sym}): ${q['price']:,.2f} ({q['change_pct']:+.2f}%) "
                    f"| Vol: {q['volume']:,}"
                )
            except Exception:
                lines.append(f"- **{name}** ({sym}): unavailable")

        # VIX
        try:
            vix = self.fetch_quote("^VIX")
            lines.append(f"- **VIX**: {vix['price']:.2f} ({vix['change_pct']:+.2f}%)")
        except Exception:
            pass

        lines.append("")

        # Sector ETFs
        sectors = {
            "XLK": "Technology", "XLV": "Healthcare", "XLF": "Financials",
            "XLE": "Energy", "XLY": "Consumer Disc.", "XLI": "Industrials",
            "XLU": "Utilities", "XLRE": "Real Estate",
        }
        lines.append("## Sector Performance")
        for sym, name in sectors.items():
            try:
                q = self.fetch_quote(sym)
                lines.append(f"- **{name}** ({sym}): ${q['price']:,.2f} ({q['change_pct']:+.2f}%)")
            except Exception:
                pass

        lines.append("")

        # Individual stocks
        lines.append("## Watchlist Quotes")
        for ticker in tickers:
            try:
                q = self.fetch_quote(ticker)
                lines.append(
                    f"- **{ticker}**: ${q['price']:,.2f} ({q['change_pct']:+.2f}%) "
                    f"| Vol: {q['volume']:,} | MCap: ${q['market_cap']/1e9:.1f}B"
                )
            except Exception:
                lines.append(f"- **{ticker}**: unavailable")

        return "\n".join(lines)

    def get_options_summary(self, ticker: str) -> str:
        """Formatted options chain summary for agents."""
        chain_data = self.fetch_options_chain(ticker)
        if not chain_data["chains"]:
            return f"No options data available for {ticker}"

        lines = [f"# {ticker} Options Chain", ""]

        try:
            quote = self.fetch_quote(ticker)
            current_price = quote["price"]
            lines.append(f"Current Price: ${current_price:,.2f}")
        except Exception:
            current_price = 0

        lines.append(f"Available Expirations: {', '.join(chain_data['expirations'][:6])}")
        lines.append("")

        for exp, chain in list(chain_data["chains"].items())[:2]:
            lines.append(f"## Expiry: {exp}")

            # Filter to near-the-money strikes
            lines.append("### Calls (near ATM)")
            for opt in chain["calls"]:
                if current_price > 0 and abs(opt["strike"] - current_price) / current_price > 0.15:
                    continue
                vol = opt.get("volume") or 0
                oi = opt.get("openInterest") or 0
                iv = opt.get("impliedVolatility", 0) * 100
                itm = "ITM" if opt.get("inTheMoney") else "OTM"
                lines.append(
                    f"  ${opt['strike']:.2f} {itm} | Last: ${opt['lastPrice']:.2f} "
                    f"| Bid/Ask: ${opt['bid']:.2f}/${opt['ask']:.2f} "
                    f"| Vol: {vol} | OI: {oi} | IV: {iv:.1f}%"
                )

            lines.append("### Puts (near ATM)")
            for opt in chain["puts"]:
                if current_price > 0 and abs(opt["strike"] - current_price) / current_price > 0.15:
                    continue
                vol = opt.get("volume") or 0
                oi = opt.get("openInterest") or 0
                iv = opt.get("impliedVolatility", 0) * 100
                itm = "ITM" if opt.get("inTheMoney") else "OTM"
                lines.append(
                    f"  ${opt['strike']:.2f} {itm} | Last: ${opt['lastPrice']:.2f} "
                    f"| Bid/Ask: ${opt['bid']:.2f}/${opt['ask']:.2f} "
                    f"| Vol: {vol} | OI: {oi} | IV: {iv:.1f}%"
                )

            lines.append("")

        return "\n".join(lines)

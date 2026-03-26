"""Market data routing — dispatches to asset-class-specific providers."""

from __future__ import annotations

import pandas as pd

from .crypto_data import CryptoMarketData
from .stock_data import StockMarketData
from ..teams.registry import TeamConfig


class MarketDataRouter:
    """Routes market data fetches to the correct provider based on asset class."""

    def __init__(self, config: TeamConfig):
        self.config = config
        if config.asset_class == "stocks":
            self._provider: StockMarketData | CryptoMarketData = StockMarketData()
        elif config.asset_class == "crypto":
            self._provider = CryptoMarketData(exchange_name=config.exchange)
        else:
            raise ValueError(f"Unknown asset_class: {config.asset_class!r}")

    def fetch_ohlcv(
        self, ticker: str, period: str = "3mo", interval: str = "1d"
    ) -> pd.DataFrame:
        """Delegate OHLCV fetch to the underlying provider."""
        return self._provider.fetch_ohlcv(ticker, period, interval)

    def fetch_quote(self, ticker: str) -> dict:
        """Delegate quote fetch to the underlying provider."""
        return self._provider.fetch_quote(ticker)

    def fetch_multiple_quotes(self, tickers: list[str]) -> dict[str, dict]:
        """Delegate multiple-quote fetch to the underlying provider."""
        return self._provider.fetch_multiple_quotes(tickers)

    def fetch_options_chain(self, ticker: str) -> dict:
        """Delegate options chain fetch to the underlying provider."""
        return self._provider.fetch_options_chain(ticker)

    def get_market_summary(self, tickers: list[str]) -> str:
        """Delegate market summary to the underlying provider."""
        return self._provider.get_market_summary(tickers)

    def get_options_summary(self, ticker: str) -> str:
        """Delegate options summary to the underlying provider."""
        return self._provider.get_options_summary(ticker)

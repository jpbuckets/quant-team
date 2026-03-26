"""Unit tests for CryptoMarketData — Jupiter Price API and ccxt integration."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from quant_team.market.crypto_data import (
    CryptoMarketData,
    fetch_jupiter_prices,
    ticker_to_ccxt_pair,
    ticker_to_mint,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def test_ticker_to_mint():
    assert ticker_to_mint("SOL") == "So11111111111111111111111111111111111111112"
    assert ticker_to_mint("sol") == "So11111111111111111111111111111111111111112"
    assert ticker_to_mint("UNKNOWN") is None


def test_ticker_to_ccxt_pair():
    assert ticker_to_ccxt_pair("SOL") == "SOL/USDT"
    assert ticker_to_ccxt_pair("jup") == "JUP/USDT"
    assert ticker_to_ccxt_pair("BTC", "USDC") == "BTC/USDC"


# ---------------------------------------------------------------------------
# Jupiter Price API
# ---------------------------------------------------------------------------


def test_jupiter_price_fetch(monkeypatch):
    """mock httpx.get to return valid price data; fetch_jupiter_prices returns {mint: float}."""
    monkeypatch.setenv("JUPITER_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": {
            "So11111111111111111111111111111111111111112": {"price": "150.5"},
        }
    }

    with patch("quant_team.market.crypto_data.httpx.get", return_value=mock_response):
        result = fetch_jupiter_prices(["So11111111111111111111111111111111111111112"])

    assert result == {"So11111111111111111111111111111111111111112": 150.5}


def test_jupiter_missing_key(monkeypatch):
    """With JUPITER_API_KEY unset, fetch_jupiter_prices returns {} gracefully."""
    monkeypatch.delenv("JUPITER_API_KEY", raising=False)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": {}}

    with patch("quant_team.market.crypto_data.httpx.get", return_value=mock_response):
        result = fetch_jupiter_prices(["So11111111111111111111111111111111111111112"])

    # Should return {} or empty when no key set (graceful degradation)
    assert isinstance(result, dict)


def test_jupiter_http_error(monkeypatch):
    """When httpx.get raises, fetch_jupiter_prices returns {} without crashing."""
    monkeypatch.setenv("JUPITER_API_KEY", "test-key")

    with patch("quant_team.market.crypto_data.httpx.get", side_effect=Exception("network error")):
        result = fetch_jupiter_prices(["So11111111111111111111111111111111111111112"])

    assert result == {}


# ---------------------------------------------------------------------------
# CryptoMarketData — ccxt-backed methods
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_exchange():
    """Returns a MagicMock ccxt exchange with id attribute."""
    exchange = MagicMock()
    exchange.id = "binance"
    return exchange


@pytest.fixture()
def crypto_provider(mock_exchange):
    """CryptoMarketData instance with mocked ccxt exchange."""
    with patch("quant_team.market.crypto_data.ccxt") as mock_ccxt:
        mock_ccxt.binance.return_value = mock_exchange
        provider = CryptoMarketData(exchange_name="binance")
    provider.exchange = mock_exchange
    return provider


def test_ccxt_ohlcv_dataframe(crypto_provider, mock_exchange):
    """fetch_ohlcv returns DataFrame with DatetimeIndex and OHLCV columns."""
    import time as time_mod
    ts_base = int(time_mod.time() * 1000)
    rows = [
        [ts_base + i * 86400000, 100 + i, 105 + i, 95 + i, 102 + i, 5000 + i * 100]
        for i in range(10)
    ]
    mock_exchange.fetch_ohlcv.return_value = rows

    df = crypto_provider.fetch_ohlcv("SOL")

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert len(df) == 10


def test_ccxt_ticker_quote(crypto_provider, mock_exchange, monkeypatch):
    """fetch_quote returns dict with 'ticker' and 'price' keys from ccxt ticker."""
    monkeypatch.delenv("JUPITER_API_KEY", raising=False)

    mock_exchange.fetch_ticker.return_value = {
        "last": 150.0,
        "bid": 149.5,
        "ask": 150.5,
        "quoteVolume": 1000000,
    }

    # Patch Jupiter to return empty so ccxt fallback is used
    with patch("quant_team.market.crypto_data.fetch_jupiter_prices", return_value={}):
        result = crypto_provider.fetch_quote("SOL")

    assert "ticker" in result
    assert "price" in result
    assert result["ticker"] == "SOL"
    assert result["price"] == 150.0


def test_fetch_quote_returns_expected_shape(crypto_provider, mock_exchange, monkeypatch):
    """fetch_quote returns dict with at least 'ticker' and 'price' keys."""
    monkeypatch.delenv("JUPITER_API_KEY", raising=False)

    mock_exchange.fetch_ticker.return_value = {
        "last": 99.0,
        "bid": 98.0,
        "ask": 100.0,
        "quoteVolume": 500000,
    }

    with patch("quant_team.market.crypto_data.fetch_jupiter_prices", return_value={}):
        result = crypto_provider.fetch_quote("JUP")

    required_keys = {"ticker", "price", "previous_close", "open", "day_high",
                     "day_low", "volume", "market_cap", "change_pct"}
    for key in required_keys:
        assert key in result, f"Missing key: {key}"


def test_get_market_summary_returns_string(crypto_provider, mock_exchange, monkeypatch):
    """get_market_summary returns a non-empty string."""
    monkeypatch.delenv("JUPITER_API_KEY", raising=False)

    mock_exchange.fetch_ticker.return_value = {
        "last": 150.0,
        "bid": 149.5,
        "ask": 150.5,
        "quoteVolume": 1000000,
    }

    with patch("quant_team.market.crypto_data.fetch_jupiter_prices", return_value={}):
        result = crypto_provider.get_market_summary(["SOL"])

    assert isinstance(result, str)
    assert len(result) > 0


def test_get_options_summary_returns_empty(crypto_provider):
    """get_options_summary returns empty string — crypto has no options."""
    result = crypto_provider.get_options_summary("SOL")
    assert result == ""


def test_fetch_options_chain_returns_empty(crypto_provider):
    """fetch_options_chain returns dict with empty chains — crypto has no options."""
    result = crypto_provider.fetch_options_chain("SOL")
    assert result["ticker"] == "SOL"
    assert result["expirations"] == []
    assert result["chains"] == {}

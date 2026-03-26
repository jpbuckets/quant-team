"""Unit tests for MarketDataRouter dispatch and TeamConfig.exchange field."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quant_team.market.router import MarketDataRouter
from quant_team.market.stock_data import StockMarketData
from quant_team.market.crypto_data import CryptoMarketData
from quant_team.teams.registry import TeamConfig


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------


def test_stocks_routes_to_stock_provider():
    """TeamConfig with asset_class='stocks' instantiates a StockMarketData provider."""
    config = TeamConfig(team_id="t", name="T", asset_class="stocks")
    router = MarketDataRouter(config)
    assert isinstance(router._provider, StockMarketData)


def test_crypto_routes_to_crypto_provider():
    """TeamConfig with asset_class='crypto' instantiates a CryptoMarketData provider."""
    config = TeamConfig(team_id="t", name="T", asset_class="crypto")
    with patch("quant_team.market.router.CryptoMarketData") as mock_cls:
        mock_cls.return_value = MagicMock(spec=CryptoMarketData)
        router = MarketDataRouter(config)
    assert isinstance(router._provider, MagicMock)
    mock_cls.assert_called_once_with(exchange_name="binance")


def test_unknown_asset_class_raises():
    """TeamConfig with unknown asset_class raises ValueError."""
    config = TeamConfig(team_id="t", name="T", asset_class="options")
    with pytest.raises(ValueError, match="Unknown asset_class"):
        MarketDataRouter(config)


# ---------------------------------------------------------------------------
# Delegation tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_provider():
    return MagicMock()


@pytest.fixture()
def router_with_mock(mock_provider):
    config = TeamConfig(team_id="t", name="T", asset_class="stocks")
    router = MarketDataRouter(config)
    router._provider = mock_provider
    return router


def test_router_delegates_fetch_quote(router_with_mock, mock_provider):
    router_with_mock.fetch_quote("AAPL")
    mock_provider.fetch_quote.assert_called_once_with("AAPL")


def test_router_delegates_fetch_ohlcv(router_with_mock, mock_provider):
    router_with_mock.fetch_ohlcv("AAPL")
    mock_provider.fetch_ohlcv.assert_called_once_with("AAPL", "3mo", "1d")


def test_router_delegates_get_market_summary(router_with_mock, mock_provider):
    router_with_mock.get_market_summary(["AAPL"])
    mock_provider.get_market_summary.assert_called_once_with(["AAPL"])


def test_router_delegates_get_options_summary(router_with_mock, mock_provider):
    router_with_mock.get_options_summary("AAPL")
    mock_provider.get_options_summary.assert_called_once_with("AAPL")


def test_router_delegates_fetch_options_chain(router_with_mock, mock_provider):
    router_with_mock.fetch_options_chain("AAPL")
    mock_provider.fetch_options_chain.assert_called_once_with("AAPL")


def test_router_delegates_fetch_multiple_quotes(router_with_mock, mock_provider):
    router_with_mock.fetch_multiple_quotes(["AAPL"])
    mock_provider.fetch_multiple_quotes.assert_called_once_with(["AAPL"])


# ---------------------------------------------------------------------------
# TeamConfig exchange field tests
# ---------------------------------------------------------------------------


def test_team_config_exchange_field():
    """TeamConfig accepts an exchange field."""
    config = TeamConfig(team_id="c", name="C", asset_class="crypto", exchange="kraken")
    assert config.exchange == "kraken"


def test_team_config_exchange_default():
    """TeamConfig defaults exchange to 'binance'."""
    config = TeamConfig(team_id="c", name="C", asset_class="crypto")
    assert config.exchange == "binance"


def test_crypto_router_uses_exchange_from_config():
    """MarketDataRouter passes exchange from TeamConfig to CryptoMarketData."""
    config = TeamConfig(team_id="c", name="C", asset_class="crypto", exchange="kraken")
    with patch("quant_team.market.router.CryptoMarketData") as mock_cls:
        mock_cls.return_value = MagicMock(spec=CryptoMarketData)
        router = MarketDataRouter(config)
    mock_cls.assert_called_once_with(exchange_name="kraken")

from unittest.mock import patch

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.ticker import (
    LiveTickerSnapshot,
    _fetch_binance_futures_ticker_direct,
    _symbol_to_binance_futures,
    fetch_live_ticker,
)


def test_symbol_to_binance_futures():
    assert _symbol_to_binance_futures("BTC/USDT:USDT") == "BTCUSDT"
    assert _symbol_to_binance_futures("ETH/USDT:USDT") == "ETHUSDT"


def test_fetch_binance_futures_ticker_direct_parses():
    raw = {
        "lastPrice": "65000.5",
        "openPrice": "64000.0",
        "bidPrice": "64999.0",
        "askPrice": "65001.0",
        "closeTime": 1_700_000_000_000,
    }
    with patch("ai_trade_advisor.datasource.ticker.get_json", return_value=raw):
        ticker = _fetch_binance_futures_ticker_direct("BTC/USDT:USDT")
    assert ticker["last"] == 65000.5
    assert ticker["percentage"] is not None


def test_fetch_live_ticker_binance_uses_direct_api():
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT")
    with (
        patch("ai_trade_advisor.datasource.ticker._fetch_binance_futures_ticker_direct") as mock_fetch,
        patch("ai_trade_advisor.config.AdvisorConfig.binance_futures", return_value=None),
    ):
        mock_fetch.return_value = {
            "last": 65000.0,
            "bid": 64999.0,
            "ask": 65001.0,
            "percentage": 1.5,
            "timestamp": 1_700_000_000_000,
        }
        result = fetch_live_ticker(cfg)
    mock_fetch.assert_called_once()
    assert mock_fetch.call_args.kwargs.get("base_url") == "https://fapi.binance.com"
    assert result.last == 65000.0
    assert result.change_pct_24h == 1.5
    assert result.source == "binance:fapi"

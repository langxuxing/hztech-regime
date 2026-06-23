"""统一数据源模块：交易所、链上、宏观、事件、预测信号等。"""
from __future__ import annotations

from ai_trade_advisor.datasource.capital_flows import build_capital_flows
from ai_trade_advisor.datasource.exchange import make_exchange, resolve_exchange_id
from ai_trade_advisor.datasource.http_client import get_json
from ai_trade_advisor.datasource.ohlcv import (
    LocalBtcDataError,
    fetch_ohlcv_ccxt,
    get_last_ohlcv_source,
    load_local_btc_1m_csvs,
    load_ohlcv,
    ohlcv_summary,
)
from ai_trade_advisor.datasource.orderbook import fetch_orderbook
from ai_trade_advisor.datasource.paths import (
    default_events_db,
    default_regime_db,
    ensure_data_layout,
    ensure_macro_layout,
    get_data_root,
    get_etf_root,
    get_macro_root,
    get_ohlcv_dir,
    get_ohlcv_root,
    REPO_ROOT,
)
from ai_trade_advisor.datasource.ticker import LiveTickerSnapshot, fetch_live_ticker

__all__ = [
    "LiveTickerSnapshot",
    "REPO_ROOT",
    "build_capital_flows",
    "default_events_db",
    "default_regime_db",
    "ensure_data_layout",
    "ensure_macro_layout",
    "fetch_live_ticker",
    "fetch_ohlcv_ccxt",
    "fetch_orderbook",
    "get_data_root",
    "get_etf_root",
    "get_json",
    "get_macro_root",
    "get_ohlcv_dir",
    "get_ohlcv_root",
    "LocalBtcDataError",
    "load_ohlcv",
    "make_exchange",
    "ohlcv_summary",
    "resolve_exchange_id",
]

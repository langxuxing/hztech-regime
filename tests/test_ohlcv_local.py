from __future__ import annotations

import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.ohlcv import (
    get_last_ohlcv_source,
    load_ohlcv,
    validate_ohlcv,
)


def test_load_ohlcv_prefers_local_btc(monkeypatch) -> None:
    cfg = AdvisorConfig(symbol="BTC/USDT:USDT", bar_minutes=30, lookback_bars=720)
    df = load_ohlcv(cfg)
    assert len(df) >= 50
    assert get_last_ohlcv_source() == "local_btc_1m_resample"
    result = validate_ohlcv(df, bar_minutes=30)
    assert result.bars == len(df)
    assert result.ohlc_violations == 0


def test_validate_ohlcv_detects_bad_rows() -> None:
    df = pd.DataFrame(
        [
            {"timestamp": 1_000_000, "open": 100, "high": 90, "low": 95, "close": 98, "volume": 1},
            {"timestamp": 1_060_000, "open": 98, "high": 101, "low": 97, "close": 100, "volume": 1},
        ]
    )
    result = validate_ohlcv(df, bar_minutes=1)
    assert result.ohlc_violations == 1
    assert not result.ok

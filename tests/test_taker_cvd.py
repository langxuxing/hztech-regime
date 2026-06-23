from __future__ import annotations

import numpy as np
import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.spot_cvd import analyze_spot_cvd_from_frames, build_spot_cvd_series
from ai_trade_advisor.datasource.taker_cvd import build_taker_cvd_series


def test_taker_cvd_delta_cumsum():
    df = pd.DataFrame(
        {
            "taker_buy_volume": [10.0, 8.0, 12.0],
            "taker_sell_volume": [6.0, 10.0, 4.0],
            "cvd_delta": [4.0, -2.0, 8.0],
        }
    )
    cvd = build_taker_cvd_series(df)
    assert list(cvd.round(2)) == [4.0, 2.0, 10.0]


def test_build_spot_cvd_series_prefers_taker():
    df = pd.DataFrame({"cvd_delta": [1.0, 2.0, -1.0]})
    out = build_spot_cvd_series(df)
    assert float(out.iloc[-1]) == 2.0


def test_analyze_spot_cvd_from_frames_breakout():
    n = 20
    ts = np.arange(n) * 1_800_000
    buy = np.linspace(5, 5, n)
    buy[-1] = 20.0
    sell = np.full(n, 4.0)
    df_30 = pd.DataFrame(
        {
            "timestamp": ts,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": buy + sell,
            "taker_buy_volume": buy,
            "taker_sell_volume": sell,
            "cvd_delta": buy - sell,
        }
    )
    df_5 = df_30.copy()
    out = analyze_spot_cvd_from_frames(
        df_30m=df_30,
        df_5m=df_5,
        perp_price=100.5,
        source="test",
    )
    assert out["source"] == "test"
    assert out["spot_cvd_breakout"] is True
    assert out["spot_premium_bps"] == 50.0

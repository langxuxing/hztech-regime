from __future__ import annotations

import pandas as pd
import pytest

from ai_trade_advisor.datasource.spot_cvd import spot_cvd_breakout
from ai_trade_advisor.regime.engine import _compose_regime, _raw_trend


def test_spot_cvd_breakout_excludes_current_bar():
    cvd = pd.Series([10.0, 12.0, 11.0, 13.0, 15.0])
    assert spot_cvd_breakout(cvd, lookback=3) is True

    flat = pd.Series([10.0, 10.0, 10.0, 10.0, 10.0])
    assert spot_cvd_breakout(flat, lookback=3) is False

    # 旧逻辑 bug：last > max(tail) 含自身 — 此处 last 等于 prior max 时应为 False
    cvd2 = pd.Series([1.0, 2.0, 3.0, 4.0, 4.0])
    assert spot_cvd_breakout(cvd2, lookback=3) is False


def test_raw_trend_kama_donchian():
    assert _raw_trend(110, 100, 90, 105, 95) == "uptrend"
    assert _raw_trend(80, 100, 90, 105, 95) == "downtrend"
    assert _raw_trend(95, 100, 90, 105, 95) == "range"


def test_compose_regime_high_vol_uptrend_requires_cvd():
    drivers: list[str] = []
    rid = _compose_regime("uptrend", "high_vol", True, False, drivers, {})
    assert rid == "high_vol_uptrend"

    drivers2: list[str] = []
    rid2 = _compose_regime("uptrend", "high_vol", False, False, drivers2, {})
    assert rid2 == "fake_breakout_wash"


def test_compose_regime_mid_vol_uptrend():
    drivers: list[str] = []
    rid = _compose_regime("uptrend", "mid_vol", False, False, drivers, {})
    assert rid == "mid_vol_uptrend"


def test_self_heal_requires_elevated_vol():
    drivers: list[str] = []
    rid = _compose_regime("downtrend", "low_vol", False, True, drivers, {})
    assert rid == "low_vol_downtrend"

    drivers2: list[str] = []
    rid2 = _compose_regime("downtrend", "high_vol", False, True, drivers2, {"spot_premium_positive": True})
    assert rid2 == "high_vol_self_heal_range"

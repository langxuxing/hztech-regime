from __future__ import annotations

import pandas as pd

from ai_trade_advisor.datasource.derivatives_trend import (
    _funding_bias,
    _oi_sync,
    cvd_trend_bias,
    resolve_trend_with_derivatives,
)


def test_cvd_trend_bias_bullish():
    cvd = pd.Series([0.0, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 30.0])
    bias, slope = cvd_trend_bias(cvd, lookback=14)
    assert bias == "bullish"
    assert slope is not None and slope > 0


def test_funding_extreme_positive_is_bearish_crowding():
    bias, _ = _funding_bias(0.001, [0.0005, 0.0007, 0.001])
    assert bias == "bearish"


def test_oi_long_build():
    bias, sync, _ = _oi_sync(price_change_pct=2.0, oi_change_pct=5.0)
    assert bias == "bullish"
    assert sync == "long_build"


def test_resolve_trend_downgrades_uptrend_on_derivative_divergence():
    drivers: list[str] = []
    deriv = {"derivative_votes_bull": 0, "derivative_votes_bear": 2}
    trend = resolve_trend_with_derivatives("uptrend", deriv, drivers)
    assert trend == "range"
    assert any("降级" in d for d in drivers)


def test_resolve_trend_upgrades_range_on_bullish_consensus():
    drivers: list[str] = []
    deriv = {"derivative_votes_bull": 3, "derivative_votes_bear": 0}
    trend = resolve_trend_with_derivatives("range", deriv, drivers)
    assert trend == "uptrend"

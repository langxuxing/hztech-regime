"""Regime 防抖单元测试。"""

from __future__ import annotations

from ai_trade_advisor.regime.confirmation import (
    apply_transition_penalty,
    confirm_regime_state,
    reset_regime_debouncer,
)
from ai_trade_advisor.regime.engine import BtcRegimeAnalysis


def _analysis(regime_id: str, *, confidence: float = 0.8) -> BtcRegimeAnalysis:
    return BtcRegimeAnalysis(
        regime_id=regime_id,
        regime_label=regime_id,
        raw_trend="range",
        vol_bucket="mid_vol",
        close=100_000.0,
        donchian_upper=101_000.0,
        donchian_lower=99_000.0,
        kama=100_000.0,
        kama_upper=100_500.0,
        kama_lower=99_500.0,
        spot_cvd=None,
        spot_cvd_breakout=False,
        cvd_bullish_divergence=False,
        spot_premium_bps=None,
        spot_premium_positive=False,
        macro_hazard=False,
        confidence=confidence,
        dashboard_regime="range",
    )


def test_transition_penalty_reduces_switch_probability():
    probs = [0.2, 0.5, 0.2, 0.1]
    adjusted, applied = apply_transition_penalty(probs, prev_state_idx=1, penalty=0.5)
    assert applied
    assert adjusted[1] > adjusted[0]
    assert abs(sum(adjusted) - 1.0) < 1e-6


def test_dwell_blocks_immediate_regime_switch():
    reset_regime_debouncer()
    key = "test:BTC"

    live = _analysis("mid_vol_range")
    stable = _analysis("mid_vol_range")
    candidate = _analysis("low_vol_uptrend")

    confirm_regime_state(symbol_key=key, live=stable, confirmed=stable, min_dwell_bars=2)

    state1 = confirm_regime_state(
        symbol_key=key,
        live=live,
        confirmed=candidate,
        min_dwell_bars=2,
    )
    assert state1.combined.confirmed_regime_id == "mid_vol_range"
    assert not state1.regime_switched

    state2 = confirm_regime_state(
        symbol_key=key,
        live=live,
        confirmed=candidate,
        min_dwell_bars=2,
    )
    assert state2.combined.confirmed_regime_id == "low_vol_uptrend"
    assert state2.regime_switched


def test_confirmed_stable_when_live_flickers():
    reset_regime_debouncer()
    key = "test:BTC:flicker"

    base = _analysis("low_vol_range")
    uptrend = _analysis("low_vol_uptrend")

    s1 = confirm_regime_state(symbol_key=key, live=uptrend, confirmed=base, min_dwell_bars=2)
    assert s1.combined.live_regime_id == "low_vol_uptrend"
    assert s1.combined.confirmed_regime_id == "low_vol_range"

    s2 = confirm_regime_state(symbol_key=key, live=base, confirmed=base, min_dwell_bars=2)
    assert s2.combined.confirmed_regime_id == "low_vol_range"


def test_split_confirmed_bars_drops_unclosed():
    import pandas as pd

    from ai_trade_advisor.layers.l1_ingestion.transform import split_confirmed_bars

    now = pd.Timestamp.now(tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": [int((now - pd.Timedelta(minutes=30)).timestamp() * 1000)] * 5
            + [int(now.timestamp() * 1000)],
            "open": [100.0] * 6,
            "high": [101.0] * 6,
            "low": [99.0] * 6,
            "close": [100.0] * 6,
            "volume": [1.0] * 6,
            "datetime": [now - pd.Timedelta(minutes=30 * i) for i in range(5, -1, -1)],
        }
    )
    result = split_confirmed_bars(df, bar_minutes=30)
    assert result.dropped_unclosed is True
    assert len(result.df_confirmed) == len(result.df_live) - 1

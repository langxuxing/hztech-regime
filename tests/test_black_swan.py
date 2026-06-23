"""黑天鹅预警单元测试。"""

from __future__ import annotations

from ai_trade_advisor.black_swan.engine import (
    apply_circuit_breaker_to_regime,
    evaluate_black_swan_alert,
)
from ai_trade_advisor.features.liquidation_grid import LiquidationGridState
from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState


def test_black_swan_normal_when_no_triggers():
    alert = evaluate_black_swan_alert(
        macro=MacroHazardState(macro_hazard_flag=False),
        liquidation_pulse={"near_notional_usd": 0, "total_weight": 0, "extreme_pulse": False},
    )
    assert alert.level == 0
    assert alert.level_label == "normal"
    assert not alert.suspended
    assert not alert.circuit_breaker_active


def test_black_swan_halt_on_macro_hazard():
    alert = evaluate_black_swan_alert(
        macro=MacroHazardState(macro_hazard_flag=True, active_events=["CPI (+5min)"]),
    )
    assert alert.level == 3
    assert alert.suspended
    assert alert.circuit_breaker_active
    assert alert.actions["position_scale"] == 0.0


def test_black_swan_warn_on_changepoint():
    alert = evaluate_black_swan_alert(
        macro=MacroHazardState(macro_hazard_flag=False),
        changepoint_prob=0.85,
    )
    assert alert.level == 2
    assert alert.circuit_breaker_active
    assert not alert.actions["allow_new_orders"]


def test_black_swan_halt_on_liq_pulse_and_oi_shock():
    alert = evaluate_black_swan_alert(
        macro=MacroHazardState(macro_hazard_flag=False),
        liquidation_pulse={
            "near_notional_usd": 8_000_000,
            "total_weight": 12_000_000,
            "extreme_pulse": True,
        },
        oi_change_pct=-5.0,
        liq_pulse_threshold_usd=5_000_000,
        liq_total_threshold_usd=10_000_000,
    )
    assert alert.level == 3
    assert any("强平" in t for t in alert.triggers)


def test_apply_circuit_breaker_overrides_regime():
    regime = {
        "regime_id": "high_vol_uptrend",
        "regime_label": "高波上涨",
        "confidence": 0.82,
        "drivers": [],
    }
    alert = evaluate_black_swan_alert(
        macro=MacroHazardState(macro_hazard_flag=True),
    )
    out = apply_circuit_breaker_to_regime(regime, alert)
    assert out["regime_id"] == "macro_frozen_range"
    assert out["black_swan"]["level"] == 3


def test_halt_persists_after_regime_merge():
    """防抖合并后，Halt 熔断不得被 confirmed regime 覆盖。"""
    from ai_trade_advisor.layers.types import CombinedRegimeStatus, ConfirmationState
    from ai_trade_advisor.regime.confirmation import merge_confirmed_into_regime_dict

    regime = {
        "regime_id": "high_vol_uptrend",
        "regime_label": "高波上涨",
        "confidence": 0.82,
        "drivers": [],
    }
    confirmation = ConfirmationState(
        combined=CombinedRegimeStatus(
            live_regime_id="high_vol_uptrend",
            confirmed_regime_id="mid_vol_range",
            regime_label="中波震荡",
            confidence=0.62,
            dashboard_regime="range",
        ),
        transition_penalty_applied=False,
        dwell_bars=2,
        min_dwell_bars=2,
        regime_switched=True,
    )
    merged = merge_confirmed_into_regime_dict(regime, confirmation)
    assert merged["regime_id"] == "mid_vol_range"

    alert = evaluate_black_swan_alert(
        macro=MacroHazardState(macro_hazard_flag=True),
    )
    final = apply_circuit_breaker_to_regime(merged, alert)
    assert final["regime_id"] == "macro_frozen_range"
    assert final["black_swan"]["level"] == 3


def test_extreme_pulse_alone_is_watch_not_warn():
    alert = evaluate_black_swan_alert(
        macro=MacroHazardState(macro_hazard_flag=False),
        liquidation_pulse={
            "near_notional_usd": 500_000,
            "total_weight": 12_000_000,
            "extreme_pulse": True,
        },
        liq_pulse_threshold_usd=5_000_000,
        liq_total_threshold_usd=10_000_000,
    )
    assert alert.level == 1
    assert not alert.circuit_breaker_active


def test_combine_alerts_takes_max_level():
    from ai_trade_advisor.black_swan.engine import BlackSwanAlert, combine_black_swan_alerts

    fast = BlackSwanAlert(level=1, level_label="watch", suspended=False, triggers=["a"])
    full = BlackSwanAlert(level=2, level_label="warn", suspended=False, triggers=["b"])
    merged = combine_black_swan_alerts(fast, full)
    assert merged.level == 2
    assert "a" in merged.triggers and "b" in merged.triggers


def test_donchian_resonance_warn():
    import pandas as pd

    from ai_trade_advisor.black_swan.strategies import _donchian_edge_signal

    price = 100_000.0
    n = 30
    df = pd.DataFrame(
        {
            "open": [price] * n,
            "high": [price * 1.002] * n,
            "low": [price * 0.998] * n,
            "close": [price] * n,
        }
    )
    df.iloc[-1, df.columns.get_loc("close")] = price * 1.0019

    alone = _donchian_edge_signal(df, range_squeeze_score=0.0)
    resonant = _donchian_edge_signal(df, range_squeeze_score=0.6)
    assert alone.level_hint == 1
    assert resonant.level_hint == 2
    assert resonant.details.get("range_squeeze_resonance") is True


def test_black_swan_watch_on_etf_deriv_divergence():
    from ai_trade_advisor.models import CapitalFlowsSnapshot, EtfFlowDay, EtfFlowSnapshot

    etf = EtfFlowSnapshot(
        asset="BTC",
        latest=EtfFlowDay(date="2026-01-01", flow_usd=80_000_000),
        total_7d_usd=200_000_000,
    )
    flows = CapitalFlowsSnapshot(btc_etf=etf)
    alert = evaluate_black_swan_alert(
        macro=MacroHazardState(macro_hazard_flag=False),
        capital_flows=flows,
        oi_change_pct=0.1,
        funding_bias="neutral",
    )
    assert alert.level == 1
    assert alert.level_label == "watch"

"""四层架构测试。"""

from __future__ import annotations

import pandas as pd

from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState
from ai_trade_advisor.features.smc import SmcSnapshot
from ai_trade_advisor.layers.l2_inference.rules import apply_hard_rules
from ai_trade_advisor.layers.l4_execution.parameter_tuning import tune_parameters
from ai_trade_advisor.layers.types import (
    CombinedRegimeStatus,
    FeatureTransformResult,
    InferenceResult,
    IngestionBundle,
)
from ai_trade_advisor.models import MarketContext
from ai_trade_advisor.regime.confirmation import confirm_regime_state, reset_regime_debouncer
from ai_trade_advisor.regime.engine import BtcRegimeAnalysis


def _minimal_inference(regime_id: str = "low_vol_range", confidence: float = 0.7) -> InferenceResult:
    return InferenceResult(
        raw=None,
        regime_id=regime_id,
        regime_label=regime_id,
        confidence=confidence,
    )


def test_regime_confirmation_dwell():
    reset_regime_debouncer("test")
    live = _btc_regime("high_vol_uptrend", "高波上涨", "trend_up", 0.85)
    # 首次建立 published 状态
    confirm_regime_state(
        symbol_key="test",
        live=live,
        confirmed=live,
        min_dwell_bars=3,
    )
    confirmed = _btc_regime("low_vol_downtrend", "低波下行", "trend_down", 0.75)
    state = confirm_regime_state(
        symbol_key="test",
        live=live,
        confirmed=confirmed,
        min_dwell_bars=3,
    )
    assert state.combined.confirmed_regime_id == "high_vol_uptrend"


def _btc_regime(regime_id: str, label: str, dashboard: str, confidence: float) -> BtcRegimeAnalysis:
    return BtcRegimeAnalysis(
        regime_id=regime_id,
        regime_label=label,
        raw_trend="uptrend",
        vol_bucket="high_vol",
        close=1.0,
        donchian_upper=1.0,
        donchian_lower=0.9,
        kama=1.0,
        kama_upper=1.0,
        kama_lower=0.9,
        spot_cvd=None,
        spot_cvd_breakout=True,
        cvd_bullish_divergence=False,
        spot_premium_bps=None,
        spot_premium_positive=False,
        macro_hazard=False,
        confidence=confidence,
        dashboard_regime=dashboard,
    )


def test_parameter_tuning_high_vol():
    regime = CombinedRegimeStatus(
        live_regime_id="high_vol_range",
        confirmed_regime_id="high_vol_range",
        regime_label="高波震荡",
        confidence=0.8,
        dashboard_regime="high_vol",
    )
    params = tune_parameters(regime)
    assert params["position_scale"] == 0.5
    assert params["grid_enabled"] is False


def test_hard_rule_macro_hazard():
    macro = MacroHazardState(
        macro_hazard_flag=True,
        window_minutes=120,
        active_events=["CPI"],
        next_event=None,
    )
    ctx = MarketContext(
        symbol="BTC/USDT:USDT",
        exchange="okx",
        timeframe="30m",
        as_of="",
        last_price=1.0,
        ohlcv_summary={},
        smc=SmcSnapshot(
            trend="neutral",
            mss_or_choch=None,
            mss_direction=0,
            nearest_ob=None,
            nearest_fvg=None,
        ),
        liquidity_levels=[],
        gex_levels=[],
        orderbook=None,
        macro_hazard_flag=True,
    )
    ing = IngestionBundle(
        ctx=ctx,
        df=pd.DataFrame(),
        transform=FeatureTransformResult(
            df_live=pd.DataFrame(),
            df_confirmed=pd.DataFrame(),
            dropped_unclosed=False,
        ),
        macro=macro,
        gex_engine=None,
        liquidation=None,  # type: ignore[arg-type]
    )
    out = apply_hard_rules(_minimal_inference(), ing)
    assert out.regime_id == "macro_frozen_range"
    assert out.hard_rule_triggered == "macro_hazard"

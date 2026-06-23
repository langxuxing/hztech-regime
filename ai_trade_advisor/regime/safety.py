"""Regime 防抖 + 黑天鹅预警：委托 black_swan.pipeline 统一编排。"""

from __future__ import annotations

import pandas as pd

from ai_trade_advisor.black_swan.engine import BlackSwanAlert
from ai_trade_advisor.black_swan.pipeline import (
    apply_black_swan_after_confirmation,
    evaluate_black_swan_confirmed,
    evaluate_black_swan_fast,
)
from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.features.liquidation_grid import LiquidationGridState
from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState
from ai_trade_advisor.layers.l1_ingestion.transform import split_confirmed_bars
from ai_trade_advisor.layers.types import IngestionBundle
from ai_trade_advisor.models import MarketContext
from ai_trade_advisor.regime.confirmation import confirm_regime_state
from ai_trade_advisor.regime.engine import analyze_btc_regime, BtcRegimeAnalysis
from ai_trade_advisor.signal.debouncer import DebouncerState

__all__ = [
    "apply_regime_safety_layer",
    "evaluate_black_swan_confirmed",
    "evaluate_black_swan_fast",
]


def apply_regime_safety_layer(
    cfg: AdvisorConfig,
    ctx: MarketContext,
    *,
    df: pd.DataFrame,
    macro: MacroHazardState,
    liquidation: LiquidationGridState,
    symbol_key: str,
    debouncer: DebouncerState | None = None,
    volatility: dict | None = None,
    microstructure: dict | None = None,
) -> BlackSwanAlert:
    """
    回测/备用路径：双轨推理 → 防抖 → 黑天鹅（与 orchestrator 逻辑一致）。
    """
    if not ctx.btc_regime:
        return evaluate_black_swan_fast(
            cfg,
            _ingestion_from_ctx(ctx, df, macro, liquidation, volatility, microstructure),
            live_raw=None,
        )

    transform = split_confirmed_bars(df, bar_minutes=cfg.bar_minutes)
    micro = microstructure or {}
    cvd = micro.get("cvd")
    deriv = micro.get("derivatives")

    live = _dict_to_analysis(ctx.btc_regime)
    if live is None:
        live = analyze_btc_regime(cfg, ctx, df=transform.df_live, macro=macro, cvd=cvd, deriv=deriv)

    confirmed = analyze_btc_regime(
        cfg,
        ctx,
        df=transform.df_confirmed,
        macro=macro,
        cvd=cvd,
        deriv=deriv,
        skip_triad=True,
    )

    confirmation = confirm_regime_state(
        symbol_key=symbol_key,
        live=live,
        confirmed=confirmed,
        min_dwell_bars=cfg.regime_min_dwell_bars,
        transition_penalty=cfg.regime_transition_penalty,
        debouncer=debouncer,
    )

    ingestion = _ingestion_from_ctx(ctx, df, macro, liquidation, volatility, microstructure, transform=transform)
    fast = evaluate_black_swan_fast(cfg, ingestion, live_raw=live)
    return apply_black_swan_after_confirmation(
        cfg,
        ctx,
        ingestion,
        confirmation,
        live_regime=ctx.btc_regime,
        live_raw=live,
        fast_alert=fast,
    )


def _ingestion_from_ctx(
    ctx: MarketContext,
    df: pd.DataFrame,
    macro: MacroHazardState,
    liquidation: LiquidationGridState,
    volatility: dict | None,
    microstructure: dict | None,
    *,
    transform=None,
) -> IngestionBundle:
    from ai_trade_advisor.layers.l1_ingestion.transform import split_confirmed_bars
    from ai_trade_advisor.layers.types import FeatureTransformResult, IngestionBundle

    if transform is None:
        transform = split_confirmed_bars(df, bar_minutes=30)
    return IngestionBundle(
        ctx=ctx,
        df=df,
        transform=transform,
        macro=macro,
        gex_engine=None,
        liquidation=liquidation,
        market={},
        volatility=volatility or {},
        microstructure=microstructure or {},
        macro_flow={},
    )


def _dict_to_analysis(data: dict) -> BtcRegimeAnalysis | None:
    try:
        return BtcRegimeAnalysis(
            regime_id=data["regime_id"],
            regime_label=data.get("regime_label", data["regime_id"]),
            raw_trend=data.get("raw_trend", "range"),
            vol_bucket=data.get("vol_bucket", "mid_vol"),
            close=float(data.get("close") or 0),
            donchian_upper=float(data.get("donchian_upper") or 0),
            donchian_lower=float(data.get("donchian_lower") or 0),
            kama=float(data.get("kama") or 0),
            kama_upper=float(data.get("kama_upper") or 0),
            kama_lower=float(data.get("kama_lower") or 0),
            spot_cvd=data.get("spot_cvd"),
            spot_cvd_breakout=bool(data.get("spot_cvd_breakout")),
            cvd_bullish_divergence=bool(data.get("cvd_bullish_divergence")),
            spot_premium_bps=data.get("spot_premium_bps"),
            spot_premium_positive=bool(data.get("spot_premium_positive")),
            macro_hazard=bool(data.get("macro_hazard")),
            confidence=float(data.get("confidence") or 0.6),
            tech_trend=data.get("tech_trend", "range"),
            funding_rate=data.get("funding_rate"),
            funding_bias=str(data.get("funding_bias") or "neutral"),
            open_interest=data.get("open_interest"),
            oi_change_pct=data.get("oi_change_pct"),
            oi_price_sync=str(data.get("oi_price_sync") or "neutral"),
            cvd_trend=str(data.get("cvd_trend") or "neutral"),
            derivatives_trend=data.get("derivatives_trend"),
            drivers=list(data.get("drivers") or []),
            dashboard_regime=data.get("dashboard_regime", "transition"),
            triad=data.get("triad"),
            models=data.get("models"),
            model_comparison=data.get("model_comparison"),
            next_regime_label=data.get("next_regime_label"),
            changepoint_prob=data.get("changepoint_prob"),
            in_regime_transition=bool(data.get("in_regime_transition")),
        )
    except (KeyError, TypeError, ValueError):
        return None

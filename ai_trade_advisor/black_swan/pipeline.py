"""黑天鹅预警编排：快变量（L3 前）+ 确认后实用策略（L3 后）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ai_trade_advisor.black_swan.engine import (
    BlackSwanAlert,
    apply_circuit_breaker_to_regime,
    combine_black_swan_alerts,
    evaluate_black_swan_alert,
)
from ai_trade_advisor.black_swan.strategies import build_practical_signals
from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.models import MarketContext
from ai_trade_advisor.regime.engine import BtcRegimeAnalysis

if TYPE_CHECKING:
    from ai_trade_advisor.layers.types import ConfirmationState, IngestionBundle


def evaluate_black_swan_fast(
    cfg: AdvisorConfig,
    ingestion: IngestionBundle,
    *,
    live_raw: BtcRegimeAnalysis | None,
    upcoming_high_impact: int = 0,
) -> BlackSwanAlert:
    """
    L2.5 快路径（L3 之前）：宏观 / 强平 / 变点 / 波动率 / ETF 纠偏。

    不含 failed_breakout 等依赖 confirmed regime 的实用策略。
    """
    micro = ingestion.microstructure
    return evaluate_black_swan_alert(
        macro=ingestion.macro,
        liquidation=ingestion.liquidation,
        liquidation_pulse=micro.get("liquidation_pulse"),
        changepoint_prob=live_raw.changepoint_prob if live_raw else None,
        dvol_leads_gk=ingestion.volatility.get("dvol_leads_gk"),
        vol_status=ingestion.volatility.get("vol_status"),
        oi_change_pct=micro.get("oi_change_pct"),
        funding_bias=micro.get("funding_bias"),
        capital_flows=ingestion.ctx.capital_flows,
        liq_pulse_threshold_usd=cfg.black_swan_liq_pulse_usd,
        liq_total_threshold_usd=cfg.black_swan_liq_total_usd,
        changepoint_warn_threshold=cfg.black_swan_changepoint_threshold,
        upcoming_high_impact=upcoming_high_impact,
        practical_signals=None,
    )


def evaluate_black_swan_confirmed(
    cfg: AdvisorConfig,
    ingestion: IngestionBundle,
    *,
    merged_regime: dict[str, Any],
    live_raw: BtcRegimeAnalysis | None,
    upcoming_high_impact: int = 0,
) -> BlackSwanAlert:
    """
    L3 之后：在防抖确认的 regime 上跑实用策略，并重新评估全量信号。
    """
    micro = ingestion.microstructure
    practical = build_practical_signals(
        ingestion.transform.df_confirmed,
        cfg=cfg,
        market=ingestion.market,
        microstructure=micro,
        volatility=ingestion.volatility,
        liquidation=ingestion.liquidation,
        regime=merged_regime,
        price=ingestion.ctx.last_price,
    )
    return evaluate_black_swan_alert(
        macro=ingestion.macro,
        liquidation=ingestion.liquidation,
        liquidation_pulse=micro.get("liquidation_pulse"),
        changepoint_prob=live_raw.changepoint_prob if live_raw else None,
        dvol_leads_gk=ingestion.volatility.get("dvol_leads_gk"),
        vol_status=ingestion.volatility.get("vol_status"),
        oi_change_pct=micro.get("oi_change_pct"),
        funding_bias=micro.get("funding_bias"),
        capital_flows=ingestion.ctx.capital_flows,
        liq_pulse_threshold_usd=cfg.black_swan_liq_pulse_usd,
        liq_total_threshold_usd=cfg.black_swan_liq_total_usd,
        changepoint_warn_threshold=cfg.black_swan_changepoint_threshold,
        upcoming_high_impact=upcoming_high_impact,
        practical_signals=practical,
    )


def apply_black_swan_after_confirmation(
    cfg: AdvisorConfig,
    ctx: MarketContext,
    ingestion: IngestionBundle,
    confirmation: ConfirmationState,
    *,
    live_regime: dict[str, Any],
    live_raw: BtcRegimeAnalysis | None,
    fast_alert: BlackSwanAlert,
    upcoming_high_impact: int = 0,
) -> BlackSwanAlert:
    """L3 防抖合并后：实用策略 + 熔断覆写（主路径与 safety 共用）。"""
    from ai_trade_advisor.regime.confirmation import merge_confirmed_into_regime_dict

    merged = merge_confirmed_into_regime_dict(live_regime, confirmation)
    ctx.regime_confirmation = confirmation.to_dict()

    confirmed_alert = evaluate_black_swan_confirmed(
        cfg,
        ingestion,
        merged_regime=merged,
        live_raw=live_raw,
        upcoming_high_impact=upcoming_high_impact,
    )
    alert = combine_black_swan_alerts(fast_alert, confirmed_alert)
    ctx.black_swan_alert = alert.to_dict()
    ctx.btc_regime = apply_circuit_breaker_to_regime(merged, alert)
    if alert.suspended:
        ctx.macro_hazard_flag = True
    return alert

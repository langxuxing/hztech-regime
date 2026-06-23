"""趋势判断业务契约：从 Regime 流水线输出构建统一对外结构。"""

from __future__ import annotations

from typing import Any, Literal

from ai_trade_advisor.regime.engine import _REGIME_LABELS

TrendDirection = Literal["uptrend", "downtrend", "range"]
Stability = Literal["confirmed", "provisional", "transition"]

_TREND_LABELS: dict[str, str] = {
    "uptrend": "上涨",
    "downtrend": "下跌",
    "range": "震荡",
}

# 业务决策矩阵（趋势 × Regime → 建议姿态）
_BUSINESS_STANCE: dict[tuple[str, str], str] = {
    ("uptrend", "low_vol_uptrend"): "顺势做多 · 低波趋势延续",
    ("uptrend", "mid_vol_uptrend"): "顺势做多 · 中波趋势延续",
    ("uptrend", "high_vol_uptrend"): "顺势做多 · 高波+CVD确认",
    ("uptrend", "fake_breakout_wash"): "减仓观望 · 假突破/缺买盘",
    ("downtrend", "low_vol_downtrend"): "顺势做空或空仓 · 低波下行",
    ("downtrend", "high_vol_downtrend"): "顺势做空 · 高波下跌延续",
    ("downtrend", "high_vol_self_heal_range"): "谨慎抄底 · CVD底背离",
    ("range", "low_vol_range"): "震荡策略 · 低波死寂",
    ("range", "mid_vol_range"): "等待突破 · 中波震荡",
    ("range", "high_vol_range"): "事件驱动 · 高波震荡",
    ("range", "macro_frozen_range"): "强制观望 · 宏观熔断",
    ("uptrend", "macro_frozen_range"): "强制观望 · 宏观熔断",
    ("downtrend", "macro_frozen_range"): "强制观望 · 宏观熔断",
}


def business_stance(trend: str, regime_id: str) -> str:
    """根据趋势与 Regime 返回业务建议姿态。"""
    key = (trend, regime_id)
    if key in _BUSINESS_STANCE:
        return _BUSINESS_STANCE[key]
    if regime_id == "macro_frozen_range":
        return "强制观望 · 宏观熔断"
    if trend == "uptrend":
        return "偏多 · 趋势跟随"
    if trend == "downtrend":
        return "偏空 · 趋势跟随"
    return "震荡 · 不做方向单"


def _stability_from_confirmation(
    btc: dict[str, Any],
    confirmation: dict[str, Any] | None,
) -> Stability:
    if btc.get("in_regime_transition"):
        return "transition"
    if btc.get("macro_hazard"):
        return "provisional"

    combined = (confirmation or btc.get("confirmation") or {}).get("combined") or {}
    live_rid = combined.get("live_regime_id") or btc.get("live_regime_id")
    confirmed_rid = combined.get("confirmed_regime_id") or btc.get("regime_id")
    if live_rid and confirmed_rid and live_rid != confirmed_rid:
        return "provisional"

    dwell = int((confirmation or {}).get("dwell_bars") or 0)
    min_dwell = int((confirmation or {}).get("min_dwell_bars") or 2)
    if dwell >= min_dwell:
        return "confirmed"
    return "provisional"


def _consensus_alignment(trend: str, consensus: dict[str, Any] | None) -> dict[str, Any] | None:
    if not consensus:
        return None
    direction = str(consensus.get("direction") or "neutral").lower()
    mapped = {"up": "uptrend", "down": "downtrend", "neutral": "range"}.get(direction, "range")
    aligned = mapped == trend or (mapped == "range" and trend == "range")
    return {
        "consensus_direction": direction,
        "consensus_label": consensus.get("label"),
        "aligned": aligned,
        "score": consensus.get("score"),
        "agreement": consensus.get("agreement"),
    }


def apply_consensus_confidence_cap(
    confidence: float,
    alignment: dict[str, Any] | None,
) -> tuple[float, bool]:
    """内部趋势与外部共识不一致时，置信度上限 0.55。"""
    if alignment and not alignment.get("aligned"):
        return min(confidence, 0.55), True
    return confidence, False


def build_trend_judgment(
    btc_regime: dict[str, Any] | None,
    *,
    regime_confirmation: dict[str, Any] | None = None,
    consensus: dict[str, Any] | None = None,
    data_tier: str = "unknown",
    hmm_modifier: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    构建对外趋势判断块。

    主信号 = 衍生品融合后的 raw_trend；Regime 来自 L3 确认后的 regime_id。
    """
    if not btc_regime:
        return None

    trend = str(btc_regime.get("raw_trend") or "range")
    tech_trend = str(btc_regime.get("tech_trend") or trend)
    regime_id = str(btc_regime.get("regime_id") or "mid_vol_range")
    confidence = float(btc_regime.get("confidence") or 0.5)
    stability = _stability_from_confirmation(btc_regime, regime_confirmation)
    alignment = _consensus_alignment(trend, consensus)
    confidence, consensus_capped = apply_consensus_confidence_cap(confidence, alignment)

    comparison = btc_regime.get("model_comparison") or {}
    needs_human = bool(comparison.get("needs_human_judgment"))

    combined = (regime_confirmation or btc_regime.get("confirmation") or {}).get("combined") or {}
    live_regime_id = combined.get("live_regime_id") or btc_regime.get("live_regime_id")

    drivers = list(btc_regime.get("drivers") or [])[:8]
    if consensus_capped:
        drivers.append("外部趋势共识与内部判断不一致 → 置信度上限 55%")
    if hmm_modifier and hmm_modifier.get("applied"):
        drivers.append(str(hmm_modifier.get("note") or "HMM 修正已应用"))

    return {
        "trend": trend,
        "trend_label": _TREND_LABELS.get(trend, trend),
        "tech_trend": tech_trend,
        "tech_trend_label": _TREND_LABELS.get(tech_trend, tech_trend),
        "confidence": round(confidence, 3),
        "regime_id": regime_id,
        "regime_label": btc_regime.get("regime_label") or _REGIME_LABELS.get(regime_id, regime_id),
        "dashboard_regime": btc_regime.get("dashboard_regime"),
        "stability": stability,
        "business_stance": business_stance(trend, regime_id),
        "drivers": drivers[:10],
        "data_tier": data_tier,
        "needs_human_judgment": needs_human,
        "in_regime_transition": bool(btc_regime.get("in_regime_transition")),
        "changepoint_prob": btc_regime.get("changepoint_prob"),
        "live_regime_id": live_regime_id,
        "confirmed_regime_id": combined.get("confirmed_regime_id") or regime_id,
        "derivatives": {
            "funding_bias": btc_regime.get("funding_bias"),
            "oi_price_sync": btc_regime.get("oi_price_sync"),
            "cvd_trend": btc_regime.get("cvd_trend"),
            "derivative_votes_bull": (btc_regime.get("derivatives_trend") or {}).get("votes_bull"),
            "derivative_votes_bear": (btc_regime.get("derivatives_trend") or {}).get("votes_bear"),
        },
        "consensus_alignment": alignment,
        "consensus_capped": consensus_capped,
        "hmm_modifier": hmm_modifier,
        "model_agreement": comparison.get("agreement_ratio"),
    }

"""趋势判断业务契约：从 Regime 流水线输出构建统一对外结构。"""

from __future__ import annotations

from typing import Any, Literal

from ai_trade_advisor.regime.labels import REGIME_LABELS

TrendDirection = Literal["uptrend", "downtrend", "range"]
Stability = Literal["confirmed", "provisional", "transition"]

_TREND_LABELS: dict[str, str] = {
    "uptrend": "上涨",
    "downtrend": "下跌",
    "range": "震荡",
}

_CONSENSUS_CAP_DEFAULT = 0.55

TREND_JUDGMENT_REQUIRED_KEYS = frozenset({
    "trend",
    "trend_label",
    "tech_trend",
    "confidence",
    "regime_id",
    "regime_label",
    "stability",
    "business_stance",
    "drivers",
    "data_tier",
    "needs_human_judgment",
    "hmm_disagrees",
    "consensus_misaligned",
    "consensus_capped",
})

VALID_TRENDS = frozenset({"uptrend", "downtrend", "range"})
VALID_STABILITY = frozenset({"confirmed", "provisional", "transition"})
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
    trend_map = {"up": "uptrend", "down": "downtrend"}
    mapped = trend_map.get(direction)
    # neutral 视为无明确反对，不触发压制
    if direction == "neutral" or mapped is None:
        opposing = False
        aligned = True
    else:
        opposing = mapped != trend
        aligned = not opposing
    return {
        "consensus_direction": direction,
        "consensus_label": consensus.get("label"),
        "aligned": aligned,
        "opposing": opposing,
        "score": consensus.get("score"),
        "agreement": consensus.get("agreement"),
    }


def apply_consensus_confidence_cap(
    confidence: float,
    alignment: dict[str, Any] | None,
    *,
    cap: float = _CONSENSUS_CAP_DEFAULT,
) -> tuple[float, bool, bool]:
    """
    外部共识与内部趋势明确相反时裁剪置信度。

    返回 (confidence, consensus_misaligned, consensus_capped)。
    consensus_capped 仅在实际降低了置信度时为 True。
    """
    if not alignment or not alignment.get("opposing"):
        return confidence, False, False
    before = confidence
    after = min(confidence, cap)
    return after, True, after < before


def validate_trend_judgment(tj: dict[str, Any] | None) -> list[str]:
    """校验 trend_judgment 契约，返回错误列表（空=通过）。"""
    if not tj:
        return ["trend_judgment is missing"]
    errors: list[str] = []
    missing = TREND_JUDGMENT_REQUIRED_KEYS - set(tj.keys())
    if missing:
        errors.append(f"missing keys: {sorted(missing)}")
    trend = tj.get("trend")
    if trend not in VALID_TRENDS:
        errors.append(f"invalid trend: {trend}")
    stability = tj.get("stability")
    if stability not in VALID_STABILITY:
        errors.append(f"invalid stability: {stability}")
    conf = tj.get("confidence")
    if not isinstance(conf, (int, float)) or not (0 <= float(conf) <= 1):
        errors.append(f"invalid confidence: {conf}")
    return errors


# 业务决策矩阵（趋势 × Regime → 建议姿态）


def _resolve_hmm_modifier(btc_regime: dict[str, Any]) -> dict[str, Any] | None:
    return btc_regime.get("hmm_modifier") or btc_regime.get("hmm_confidence_modifier")


def _append_driver(drivers: list[str], note: str) -> None:
    if note and note not in drivers:
        drivers.append(note)


def build_trend_judgment(
    btc_regime: dict[str, Any] | None,
    *,
    regime_confirmation: dict[str, Any] | None = None,
    consensus: dict[str, Any] | None = None,
    data_tier: str = "unknown",
    hmm_modifier: dict[str, Any] | None = None,
    consensus_cap: float = _CONSENSUS_CAP_DEFAULT,
) -> dict[str, Any] | None:
    """
    构建对外趋势判断块。

    主信号 = 衍生品融合后的 raw_trend；Regime 来自 L3 确认后的 regime_id。
    """
    if not btc_regime:
        return None

    hmm_modifier = hmm_modifier or _resolve_hmm_modifier(btc_regime)

    trend = str(btc_regime.get("raw_trend") or "range")
    tech_trend = str(btc_regime.get("tech_trend") or trend)
    regime_id = str(btc_regime.get("regime_id") or "mid_vol_range")
    confidence = float(btc_regime.get("confidence") or 0.5)
    stability = _stability_from_confirmation(btc_regime, regime_confirmation)
    alignment = _consensus_alignment(trend, consensus)
    confidence, consensus_misaligned, consensus_capped = apply_consensus_confidence_cap(
        confidence, alignment, cap=consensus_cap
    )

    comparison = btc_regime.get("model_comparison") or {}
    needs_human = bool(comparison.get("needs_human_judgment"))
    hmm_disagrees = bool(
        btc_regime.get("hmm_disagrees") or (hmm_modifier or {}).get("disagrees")
    )

    combined = (regime_confirmation or btc_regime.get("confirmation") or {}).get("combined") or {}
    live_regime_id = combined.get("live_regime_id") or btc_regime.get("live_regime_id")

    drivers = list(btc_regime.get("drivers") or [])[:8]
    if consensus_capped:
        _append_driver(drivers, "外部趋势共识与内部判断相反 → 置信度上限 55%")
    elif consensus_misaligned:
        _append_driver(drivers, "外部趋势共识与内部判断存在分歧")

    return {
        "trend": trend,
        "trend_label": _TREND_LABELS.get(trend, trend),
        "tech_trend": tech_trend,
        "tech_trend_label": _TREND_LABELS.get(tech_trend, tech_trend),
        "confidence": round(confidence, 3),
        "regime_id": regime_id,
        "regime_label": btc_regime.get("regime_label") or REGIME_LABELS.get(regime_id, regime_id),
        "dashboard_regime": btc_regime.get("dashboard_regime"),
        "stability": stability,
        "business_stance": business_stance(trend, regime_id),
        "drivers": drivers[:10],
        "data_tier": data_tier,
        "needs_human_judgment": needs_human,
        "in_regime_transition": bool(btc_regime.get("in_regime_transition")),
        "hmm_disagrees": hmm_disagrees,
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
        "consensus_misaligned": consensus_misaligned,
        "consensus_capped": consensus_capped,
        "hmm_modifier": hmm_modifier,
        "model_agreement": comparison.get("agreement_ratio"),
    }

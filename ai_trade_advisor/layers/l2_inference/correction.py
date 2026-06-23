"""L2 慢变量对快变量的纠偏：ETF / 宏观修正 HMM 输出。"""

from __future__ import annotations

from typing import Any

from ai_trade_advisor.layers.types import IngestionBundle, InferenceResult


def apply_slow_variable_correction(
    inference: InferenceResult,
    ingestion: IngestionBundle,
) -> InferenceResult:
    """
    ETF 净流入与衍生品死寂时的纠偏：
    - ETF z-score > 1.5 且衍生品趋势弱 → 拉回趋势上行
    - ETF z-score < -1.5 → 抑制虚假弱趋势
  """
    corrections: list[str] = list(inference.corrections)
    etf_z = ingestion.macro_flow.get("etf_flow_zscore")
    deriv = ingestion.microstructure.get("derivatives") or {}
    bull = int(deriv.get("derivative_votes_bull") or 0)
    bear = int(deriv.get("derivative_votes_bear") or 0)
    deriv_weak = bull < 2 and bear < 2

    regime_id = inference.regime_id
    confidence = inference.confidence

    if etf_z is not None and etf_z > 1.5 and deriv_weak:
        if regime_id.endswith("_range") or regime_id == "fake_breakout_wash":
            regime_id = "low_vol_uptrend"
            confidence = min(0.88, confidence + 0.06)
            corrections.append(f"ETF 净流入 z={etf_z:.2f} 纠偏：慢变量买盘覆盖衍生品死寂")

    if etf_z is not None and etf_z < -1.5:
        if regime_id in ("low_vol_uptrend", "mid_vol_uptrend"):
            regime_id = "mid_vol_range"
            confidence = max(0.55, confidence - 0.08)
            corrections.append(f"ETF 净流出 z={etf_z:.2f} 纠偏：抑制虚假上行趋势")

    dvol_leads = ingestion.volatility.get("dvol_leads_gk")
    if dvol_leads and regime_id.endswith("_range"):
        regime_id = "high_vol_range"
        confidence = min(0.85, confidence + 0.05)
        corrections.append("DVOL 领先 GK 实现波动 → 提前预警高波震荡")

    label = inference.regime_label
    if regime_id != inference.regime_id and inference.raw:
        from ai_trade_advisor.regime.engine import _REGIME_LABELS

        label = _REGIME_LABELS.get(regime_id, regime_id)

    return InferenceResult(
        raw=inference.raw,
        regime_id=regime_id,
        regime_label=label,
        confidence=confidence,
        model_probs=inference.model_probs,
        hard_rule_triggered=inference.hard_rule_triggered,
        corrections=corrections,
        in_transition=inference.in_transition,
    )


def verify_cvd_breakout(
    inference: InferenceResult,
    ingestion: IngestionBundle,
) -> InferenceResult:
    """唐奇安突破 + CVD 验证：阳性真突破 vs 阴性假突破。"""
    micro = ingestion.microstructure
    market = ingestion.market
    close = float(market.get("close") or 0)
    d_upper = float(market.get("donchian_upper") or 0)
    cvd_breakout = bool(micro.get("spot_cvd_breakout"))
    corrections = list(inference.corrections)

    if close > d_upper and not cvd_breakout and inference.regime_id in (
        "high_vol_uptrend",
        "low_vol_uptrend",
        "mid_vol_uptrend",
    ):
        corrections.append("价格突破唐奇安但 CVD 未确认 → 锁定假突破/高波震荡")
        return InferenceResult(
            raw=inference.raw,
            regime_id="fake_breakout_wash",
            regime_label="假突破洗盘 · 缺现货买盘",
            confidence=min(inference.confidence, 0.72),
            model_probs=inference.model_probs,
            hard_rule_triggered="cvd_divergence",
            corrections=corrections,
            in_transition=inference.in_transition,
        )

    if close > d_upper and cvd_breakout:
        corrections.append("唐奇安突破 + CVD 创新高 → 阳性真突破确认")

    return InferenceResult(
        raw=inference.raw,
        regime_id=inference.regime_id,
        regime_label=inference.regime_label,
        confidence=inference.confidence,
        model_probs=inference.model_probs,
        hard_rule_triggered=inference.hard_rule_triggered,
        corrections=corrections,
        in_transition=inference.in_transition,
    )

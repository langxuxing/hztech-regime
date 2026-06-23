"""L2 硬规则校验与秒级超前触发。"""

from __future__ import annotations

from ai_trade_advisor.layers.types import IngestionBundle, InferenceResult


def apply_hard_rules(
    inference: InferenceResult,
    ingestion: IngestionBundle,
) -> InferenceResult:
    """爆仓脉冲 / 宏观熔断等确定性规则直接切入特定状态。"""
    if ingestion.macro.macro_hazard_flag:
        return InferenceResult(
            raw=inference.raw,
            regime_id="macro_frozen_range",
            regime_label="宏观熔断 · 强制观望",
            confidence=0.90,
            model_probs=inference.model_probs,
            hard_rule_triggered="macro_hazard",
            corrections=list(inference.corrections) + ["宏观事件窗口硬熔断"],
            in_transition=False,
        )

    liq = ingestion.microstructure.get("liquidation_pulse") or {}
    if liq.get("extreme_pulse"):
        return InferenceResult(
            raw=inference.raw,
            regime_id="high_vol_range",
            regime_label="高波震荡 · 事件驱动",
            confidence=0.85,
            model_probs=inference.model_probs,
            hard_rule_triggered="liquidation_pulse",
            corrections=list(inference.corrections)
            + [f"强平脉冲极端：near=${liq.get('near_notional_usd', 0):,.0f}"],
            in_transition=True,
        )

    return inference

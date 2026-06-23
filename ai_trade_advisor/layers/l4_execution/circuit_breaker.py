"""L4 黑天鹅熔断器：宏观事件 / 极端状态强行挂起。"""

from __future__ import annotations

from ai_trade_advisor.layers.types import ConfirmationState, IngestionBundle


def evaluate_circuit_breaker(
    ingestion: IngestionBundle,
    confirmation: ConfirmationState,
) -> tuple[bool, str | None]:
    """遇到宏观重大事件或极端熔断条件时，绕过模型直接挂起。"""
    if ingestion.macro.macro_hazard_flag:
        events = ingestion.macro.active_events or []
        reason = f"宏观熔断：{', '.join(events[:2])}" if events else "宏观公布窗口 ±120min"
        return True, reason

    confirmed = confirmation.combined.confirmed_regime_id
    if confirmed == "macro_frozen_range":
        return True, "Regime 确认宏观熔断状态"

    liq = ingestion.microstructure.get("liquidation_pulse") or {}
    if liq.get("extreme_pulse") and confirmation.combined.confidence >= 0.85:
        return True, "极端强平脉冲 + 高置信度 → 临时挂起新开仓"

    return False, None

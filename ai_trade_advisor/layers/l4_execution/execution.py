"""L4 业务执行与策略路由层。"""

from __future__ import annotations

from typing import Any

from ai_trade_advisor.black_swan.engine import BlackSwanAlert
from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.features.feature_aggregator import FeatureSnapshot
from ai_trade_advisor.layers.types import ConfirmationState, ExecutionPlan, IngestionBundle
from ai_trade_advisor.models import TradeAdvice
from ai_trade_advisor.state_machine import build_quant_state_machine


def run_execution(
    cfg: AdvisorConfig,
    ingestion: IngestionBundle,
    confirmation: ConfirmationState,
    alert: BlackSwanAlert,
    *,
    advice: TradeAdvice | None = None,
    feature_snapshot: FeatureSnapshot | None = None,
    upcoming_high_impact: int = 0,
) -> ExecutionPlan:
    """构建量化状态机输出，并叠加黑天鹅熔断指令。"""
    ctx = ingestion.ctx
    rel = feature_snapshot.relative if feature_snapshot else None

    quant = build_quant_state_machine(
        ctx,
        macro=ingestion.macro,
        gex_engine=ingestion.gex_engine,
        liquidation=ingestion.liquidation,
        feature_relative=rel,
        upcoming_high_impact=upcoming_high_impact,
    )

    commands = list(quant.system_commands)
    param_adj: dict[str, Any] = {}

    if alert.level >= 1:
        param_adj["position_scale"] = alert.actions["position_scale"]
        param_adj["widen_stop_multiplier"] = alert.actions["widen_stop_multiplier"]
        param_adj["confidence_multiplier"] = alert.actions["confidence_multiplier"]

    if alert.level >= 2:
        commands.insert(0, "黑天鹅 Warn: 禁止新开仓")
        if quant.okx_strategy:
            param_adj["grid_enabled"] = False
            param_adj["cta_position_scale"] = alert.actions["position_scale"]

    if alert.level >= 3:
        commands = ["全策略挂起", "黑天鹅 Halt: 熔断"]
        param_adj["suspended"] = True
        param_adj["position_scale"] = 0.0
        quant.diagnosis_id = "black_swan_halt"
        quant.diagnosis = "黑天鹅熔断市"

    if confirmation.advice_locked:
        commands.append("信号冷却锁仓中")

    quant.system_commands = commands

    return ExecutionPlan(
        quant_state=quant,
        routing_commands=commands,
        parameter_adjustments=param_adj,
        circuit_breaker_active=alert.circuit_breaker_active,
        suspended=alert.suspended,
        suspend_reason=alert.suspend_reason,
    )

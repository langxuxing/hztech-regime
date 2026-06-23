"""L4 业务执行与策略路由层编排。"""

from __future__ import annotations

from ai_trade_advisor.features.deribit_gex_engine import GexEngineResult
from ai_trade_advisor.features.feature_aggregator import build_feature_snapshot
from ai_trade_advisor.features.liquidation_grid import LiquidationGridState
from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState
from ai_trade_advisor.layers.l4_execution.circuit_breaker import evaluate_circuit_breaker
from ai_trade_advisor.layers.l4_execution.parameter_tuning import tune_parameters
from ai_trade_advisor.layers.types import ConfirmationState, ExecutionPlan, IngestionBundle
from ai_trade_advisor.signal.debouncer import DebouncerState
from ai_trade_advisor.state_machine import build_quant_state_machine


def run_execution(
    ingestion: IngestionBundle,
    confirmation: ConfirmationState,
    *,
    debouncer: DebouncerState | None = None,
) -> ExecutionPlan:
    """策略路由 + 参数微调 + 熔断挂起。"""
    ctx = ingestion.ctx
    rel_snapshot = build_feature_snapshot(
        ctx,
        macro=ingestion.macro,
        gex_engine=ingestion.gex_engine,
        liquidation=ingestion.liquidation,
        debouncer=debouncer,
    )
    ctx.feature_snapshot = rel_snapshot.to_dict()

    quant_state = build_quant_state_machine(
        ctx,
        macro=ingestion.macro,
        gex_engine=ingestion.gex_engine,
        liquidation=ingestion.liquidation,
        feature_relative=rel_snapshot.relative,
    )
    ctx.quant_state = quant_state.to_dict()

    params = tune_parameters(confirmation.combined)
    breaker, reason = evaluate_circuit_breaker(ingestion, confirmation)
    suspended = breaker or params.get("position_scale", 1.0) == 0.0

    routing = list(quant_state.system_commands)
    if suspended and reason:
        routing = [f"挂起交易：{reason}"] + routing
    elif params.get("grid_enabled") is False:
        routing.append("关闭网格")
    if params.get("cta_enabled"):
        routing.append("开启 CTA")
    if params.get("position_scale", 1.0) < 1.0:
        scale = params["position_scale"]
        routing.append(f"仓位缩放 ×{scale}")

    # 去重保序
    seen: set[str] = set()
    routing_unique = []
    for cmd in routing:
        if cmd not in seen:
            seen.add(cmd)
            routing_unique.append(cmd)

    return ExecutionPlan(
        quant_state=quant_state,
        routing_commands=routing_unique,
        parameter_adjustments=params,
        circuit_breaker_active=breaker,
        suspended=suspended,
        suspend_reason=reason,
    )

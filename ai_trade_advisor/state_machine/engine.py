from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_trade_advisor.features.deribit_gex_engine import GexEngineResult
from ai_trade_advisor.features.liquidation_grid import LiquidationGridState
from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState
from ai_trade_advisor.models import MarketContext
from ai_trade_advisor.state_machine.okx_strategies import OkxStrategyPlan, build_okx_strategy_plan
from ai_trade_advisor.state_machine.routing import (
    DailySopRule,
    RouteResult,
    WeeklyPolicy,
    build_weekly_policy,
    evaluate_daily_sop,
    resolve_route,
)
from ai_trade_advisor.state_machine.scores import (
    compute_boundaries,
    score_event_risk,
    score_flow,
    score_gex,
    score_macro,
)


@dataclass
class QuantStateSnapshot:
    """PDF 量化状态机完整快照：三因子得分 + 路由 + SOP。"""

    macro_score: int
    flow_score: int
    gex_score: int
    score_vector: list[int]
    score_label: str
    event_risk: str
    event_risk_score: int
    diagnosis_id: str
    diagnosis: str
    system_commands: list[str]
    match_type: str
    matrix_quadrant: str | None
    boundaries: dict[str, Any]
    weekly_policy: WeeklyPolicy
    daily_sop: list[DailySopRule]
    okx_strategy: OkxStrategyPlan | None = None
    drivers: list[str] = field(default_factory=list)
    philosophy: str = "放弃预测，拥抱应对"

    def to_dict(self) -> dict[str, Any]:
        return {
            "macro_score": self.macro_score,
            "flow_score": self.flow_score,
            "gex_score": self.gex_score,
            "score_vector": self.score_vector,
            "score_label": self.score_label,
            "event_risk": self.event_risk,
            "event_risk_score": self.event_risk_score,
            "diagnosis_id": self.diagnosis_id,
            "diagnosis": self.diagnosis,
            "system_commands": self.system_commands,
            "match_type": self.match_type,
            "matrix_quadrant": self.matrix_quadrant,
            "boundaries": self.boundaries,
            "weekly_policy": self.weekly_policy.to_dict(),
            "daily_sop": [r.to_dict() for r in self.daily_sop],
            "okx_strategy": self.okx_strategy.to_dict() if self.okx_strategy else None,
            "drivers": self.drivers,
            "philosophy": self.philosophy,
        }


def build_quant_state_machine(
    ctx: MarketContext,
    *,
    macro: MacroHazardState | None = None,
    gex_engine: GexEngineResult | None = None,
    liquidation: LiquidationGridState | None = None,
    feature_relative: dict[str, Any] | None = None,
    upcoming_high_impact: int = 0,
) -> QuantStateSnapshot:
    rel = feature_relative
    if rel is None and ctx.feature_snapshot:
        rel = ctx.feature_snapshot.get("relative") or {}

    macro_score, macro_drv = score_macro(ctx, macro=macro)
    flow_score, flow_drv = score_flow(ctx)
    gex_score, gex_drv = score_gex(ctx, gex_engine=gex_engine, feature_relative=rel)
    event_risk, event_score, event_drv = score_event_risk(
        macro,
        upcoming_high_impact=upcoming_high_impact,
    )

    vector = [macro_score, flow_score, gex_score]
    route = resolve_route(macro_score, flow_score, gex_score)
    boundaries = compute_boundaries(
        ctx,
        gex_engine=gex_engine,
        liquidation=liquidation,
        feature_relative=rel,
    )
    weekly = build_weekly_policy(macro_score, event_risk, route)
    daily = evaluate_daily_sop(
        gex_score,
        flow_score,
        dist_to_pain_liq_pct=rel.get("dist_to_pain_liq_pct") if rel else None,
    )
    okx_strategy = build_okx_strategy_plan(
        route,
        spot=ctx.last_price,
        boundaries=boundaries,
        weekly_policy=weekly,
        event_risk=event_risk,
    )

    drivers = list(
        dict.fromkeys(
            macro_drv + flow_drv + gex_drv + event_drv + [f"路由匹配: {route.match_type}"]
        )
    )[:14]

    return QuantStateSnapshot(
        macro_score=macro_score,
        flow_score=flow_score,
        gex_score=gex_score,
        score_vector=vector,
        score_label=_format_score_label(vector),
        event_risk=event_risk,
        event_risk_score=event_score,
        diagnosis_id=route.diagnosis_id,
        diagnosis=route.diagnosis,
        system_commands=route.system_commands,
        match_type=route.match_type,
        matrix_quadrant=route.matrix_quadrant,
        boundaries=boundaries,
        weekly_policy=weekly,
        daily_sop=daily,
        okx_strategy=okx_strategy,
        drivers=drivers,
    )


def _format_score_label(vector: list[int]) -> str:
    parts = []
    for name, val in zip(("Macro", "Flow", "Gex"), vector):
        sign = f"+{val}" if val > 0 else str(val)
        parts.append(f"${name}={sign}")
    return " ".join(parts)

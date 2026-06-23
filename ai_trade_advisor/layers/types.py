from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ai_trade_advisor.features.deribit_gex_engine import GexEngineResult
from ai_trade_advisor.features.liquidation_grid import LiquidationGridState
from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState
from ai_trade_advisor.models import MarketContext, TradeAdvice
from ai_trade_advisor.regime.engine import BtcRegimeAnalysis
from ai_trade_advisor.signal.debouncer import DebouncerState
from ai_trade_advisor.state_machine.engine import QuantStateSnapshot


@dataclass
class FeatureTransformResult:
    """L1 特征变频清洗：已确认 K 线 vs 实时末根。"""

    df_live: pd.DataFrame
    df_confirmed: pd.DataFrame
    dropped_unclosed: bool
    rate_of_change: dict[str, float | None] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "confirmed_bars": len(self.df_confirmed),
            "live_bars": len(self.df_live),
            "dropped_unclosed": self.dropped_unclosed,
            "rate_of_change": self.rate_of_change,
            "notes": self.notes,
        }


@dataclass
class IngestionBundle:
    """L1 多源数据输入层聚合。"""

    ctx: MarketContext
    df: pd.DataFrame
    transform: FeatureTransformResult
    macro: MacroHazardState
    gex_engine: GexEngineResult | None
    liquidation: LiquidationGridState
    market: dict[str, Any] = field(default_factory=dict)
    volatility: dict[str, Any] = field(default_factory=dict)
    microstructure: dict[str, Any] = field(default_factory=dict)
    macro_flow: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transform": self.transform.to_dict(),
            "market": self.market,
            "volatility": self.volatility,
            "microstructure": self.microstructure,
            "macro_flow": self.macro_flow,
            "macro_hazard": self.macro.macro_hazard_flag,
        }


@dataclass
class InferenceResult:
    """L2 状态识别与推理分类层输出。"""

    raw: BtcRegimeAnalysis | None
    regime_id: str
    regime_label: str
    confidence: float
    model_probs: dict[str, float] | None = None
    hard_rule_triggered: str | None = None
    corrections: list[str] = field(default_factory=list)
    in_transition: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime_id": self.regime_id,
            "regime_label": self.regime_label,
            "confidence": round(self.confidence, 3),
            "model_probs": self.model_probs,
            "hard_rule_triggered": self.hard_rule_triggered,
            "corrections": self.corrections,
            "in_transition": self.in_transition,
            "raw": self.raw.to_dict() if self.raw else None,
        }


@dataclass
class CombinedRegimeStatus:
    """L2+L3 统一状态输出（防抖前/后）。"""

    live_regime_id: str
    confirmed_regime_id: str
    regime_label: str
    confidence: float
    dashboard_regime: str
    drivers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "live_regime_id": self.live_regime_id,
            "confirmed_regime_id": self.confirmed_regime_id,
            "regime_label": self.regime_label,
            "confidence": round(self.confidence, 3),
            "dashboard_regime": self.dashboard_regime,
            "drivers": self.drivers,
        }


@dataclass
class ConfirmationState:
    """L3 信号防抖与合规清洗层状态。"""

    combined: CombinedRegimeStatus
    transition_penalty_applied: bool
    dwell_bars: int
    min_dwell_bars: int
    regime_switched: bool
    debouncer: DebouncerState | None = None
    advice_locked: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "combined": self.combined.to_dict(),
            "transition_penalty_applied": self.transition_penalty_applied,
            "dwell_bars": self.dwell_bars,
            "min_dwell_bars": self.min_dwell_bars,
            "regime_switched": self.regime_switched,
            "debouncer": self.debouncer.to_dict() if self.debouncer else None,
            "advice_locked": self.advice_locked,
            "notes": self.notes,
        }


@dataclass
class ExecutionPlan:
    """L4 业务执行与策略路由层输出。"""

    quant_state: QuantStateSnapshot
    routing_commands: list[str]
    parameter_adjustments: dict[str, Any]
    circuit_breaker_active: bool
    suspended: bool
    suspend_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "quant_state": self.quant_state.to_dict(),
            "routing_commands": self.routing_commands,
            "parameter_adjustments": self.parameter_adjustments,
            "circuit_breaker_active": self.circuit_breaker_active,
            "suspended": self.suspended,
            "suspend_reason": self.suspend_reason,
        }


@dataclass
class PipelineMetadata:
    """五段业务流拓扑元数据（供 UI / API 展示）。"""

    stage: str
    layers: dict[str, Any] = field(default_factory=dict)
    flow: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "layers": self.layers,
            "flow": self.flow,
        }


@dataclass
class RegimePipelineResult:
    """完整四层流水线结果。"""

    ingestion: IngestionBundle
    inference: InferenceResult
    confirmation: ConfirmationState
    execution: ExecutionPlan
    advice: TradeAdvice
    metadata: PipelineMetadata

    def to_dict(self) -> dict[str, Any]:
        return {
            "ingestion": self.ingestion.to_dict(),
            "inference": self.inference.to_dict(),
            "confirmation": self.confirmation.to_dict(),
            "execution": self.execution.to_dict(),
            "metadata": self.metadata.to_dict(),
        }

"""四层 Regime 引擎：数据输入 → 状态推理 → 信号确认 → 执行路由。"""

from ai_trade_advisor.layers.types import (
    CombinedRegimeStatus,
    ConfirmationState,
    ExecutionPlan,
    FeatureTransformResult,
    IngestionBundle,
    InferenceResult,
    PipelineMetadata,
    RegimePipelineResult,
)

__all__ = [
    "CombinedRegimeStatus",
    "ConfirmationState",
    "ExecutionPlan",
    "FeatureTransformResult",
    "IngestionBundle",
    "InferenceResult",
    "PipelineMetadata",
    "RegimePipelineResult",
    "run_regime_pipeline",
]


def __getattr__(name: str):
    if name == "run_regime_pipeline":
        from ai_trade_advisor.layers.orchestrator import run_regime_pipeline

        return run_regime_pipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

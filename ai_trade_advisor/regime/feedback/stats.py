"""人工反馈闭环统计：样本量与推荐模型就绪度。"""

from __future__ import annotations

from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.regime.feedback.store import FeedbackStore
from ai_trade_advisor.regime.judgment_store import HumanJudgmentStore

RECOMMENDATION_MIN_JUDGMENTS = 30


def build_feedback_stats(
    *,
    symbol: str,
    cfg: AdvisorConfig,
    judgment_store: HumanJudgmentStore | None = None,
    feedback_store: FeedbackStore | None = None,
    min_judgments: int = RECOMMENDATION_MIN_JUDGMENTS,
) -> dict[str, Any]:
    """汇总人工标注样本与是否可依赖推荐模型。"""
    judgment_store = judgment_store or HumanJudgmentStore()
    feedback_store = feedback_store or FeedbackStore()

    judgment_count = judgment_store.count(symbol=symbol)
    forward_scored = judgment_store.count_forward_scored(symbol=symbol)
    latest = judgment_store.latest(symbol)
    leaderboard = feedback_store.leaderboard(symbol=symbol, window_days=cfg.regime_rollup_window_days)
    eligible_models = [
        r
        for r in leaderboard
        if not r.get("low_confidence") and (r.get("sample_count") or 0) >= 8
    ]

    min_forward = max(3, cfg.regime_forward_min_samples // 4)
    recommendation_ready = (
        judgment_count >= min_judgments
        and forward_scored >= min_forward
        and len(eligible_models) > 0
    )

    if recommendation_ready:
        message = "样本充足，可评估开启 REGIME_USE_RECOMMENDATION"
    elif judgment_count < min_judgments:
        message = f"还需 {min_judgments - judgment_count} 条人工判断（当前 {judgment_count}）"
    elif forward_scored < min_forward:
        message = f"延迟打分样本不足（{forward_scored}/{min_forward}），请运行反馈 worker"
    else:
        message = "Leaderboard 样本不足，继续积累人工判断"

    return {
        "symbol": symbol,
        "judgment_count": judgment_count,
        "forward_scored_count": forward_scored,
        "min_judgments_for_recommendation": min_judgments,
        "min_forward_scored": min_forward,
        "regime_use_recommendation": cfg.regime_use_recommendation,
        "recommendation_ready": recommendation_ready,
        "eligible_model_count": len(eligible_models),
        "latest_judgment_at": latest.get("recorded_at") if latest else None,
        "message": message,
    }


def should_apply_recommendation_fusion(
    cfg: AdvisorConfig,
    recommendation: dict[str, Any] | None,
    *,
    stats: dict[str, Any] | None = None,
    judgment_store: HumanJudgmentStore | None = None,
    feedback_store: FeedbackStore | None = None,
) -> bool:
    """是否将 Leaderboard 推荐融入 ensemble（需 env 开启且样本达标）。"""
    if not cfg.regime_use_recommendation:
        return False
    if not recommendation or not recommendation.get("best_model_id"):
        return False
    if recommendation.get("low_confidence"):
        return False
    stats = stats or build_feedback_stats(
        symbol=cfg.symbol,
        cfg=cfg,
        judgment_store=judgment_store,
        feedback_store=feedback_store,
    )
    return bool(stats.get("recommendation_ready"))

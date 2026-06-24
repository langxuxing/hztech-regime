"""生产门禁：就绪度 + 趋势健康 + 人工反馈样本量。"""

from __future__ import annotations

from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.readiness import check_readiness
from ai_trade_advisor.regime.feedback.stats import RECOMMENDATION_MIN_JUDGMENTS, build_feedback_stats
from ai_trade_advisor.regime.judgment_store import HumanJudgmentStore
from ai_trade_advisor.regime.trend_health import run_trend_health_check


def run_production_gate(
    cfg: AdvisorConfig,
    *,
    min_judgments: int = RECOMMENDATION_MIN_JUDGMENTS,
    require_production: bool = False,
) -> dict[str, Any]:
    readiness = check_readiness(cfg)
    health = run_trend_health_check(cfg)
    feedback = build_feedback_stats(
        symbol=cfg.symbol,
        cfg=cfg,
        judgment_store=HumanJudgmentStore(),
        min_judgments=min_judgments,
    )

    blockers: list[str] = []
    warnings: list[str] = []

    if health.get("status") == "critical":
        blockers.append("趋势健康 critical")
    elif health.get("status") == "degraded":
        warnings.append("趋势健康 degraded")

    if require_production and readiness.tier != "production":
        blockers.append(f"就绪度 {readiness.tier}，需要 production")

    if feedback["judgment_count"] < min_judgments:
        warnings.append(
            f"人工判断样本 {feedback['judgment_count']}/{min_judgments}"
        )

    if not feedback["recommendation_ready"] and cfg.regime_use_recommendation:
        warnings.append("REGIME_USE_RECOMMENDATION 已开但样本未就绪")

    passed = len(blockers) == 0
    return {
        "passed": passed,
        "readiness_tier": readiness.tier,
        "trend_health_status": health.get("status"),
        "feedback": feedback,
        "blockers": blockers,
        "warnings": warnings,
    }

from __future__ import annotations

from collections import Counter
from typing import Any

from ai_trade_advisor.regime.feedback.params_store import ModelParamsCache
from ai_trade_advisor.regime.models.base import MODEL_CATALOG


def fuse_with_leaderboard(
    comparison: dict[str, Any],
    models: dict[str, Any],
    recommendation: dict[str, Any] | None,
    *,
    use_recommendation: bool = True,
) -> dict[str, Any]:
    """用 Leaderboard 推荐模型修正 consensus（可选）。"""
    if not use_recommendation or not recommendation:
        return comparison

    best_id = recommendation.get("best_model_id")
    if not best_id or recommendation.get("low_confidence"):
        comparison = dict(comparison)
        comparison["recommendation_note"] = recommendation.get("reason", "")
        return comparison

    best = models.get(best_id) or {}
    if not best or best.get("error"):
        return comparison

    out = dict(comparison)
    out["dominant_trend"] = best.get("raw_trend") or out.get("dominant_trend")
    out["dominant_dashboard"] = best.get("dashboard_regime") or out.get("dominant_dashboard")
    out["recommended_model_id"] = best_id
    out["recommended_model_name"] = MODEL_CATALOG.get(best_id, best_id)
    out["recommendation_note"] = recommendation.get("reason", "")
    out["summary"] = (
        f"{out.get('summary', '')} 推荐模型→{best_id} ({best.get('regime_label', '')})"
    ).strip()
    return out

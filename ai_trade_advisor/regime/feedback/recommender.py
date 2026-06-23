from __future__ import annotations

from typing import Any

from ai_trade_advisor.regime.feedback.store import FeedbackStore
from ai_trade_advisor.regime.models.base import MODEL_CATALOG


def recommend_model(
    market_context: dict[str, Any],
    *,
    symbol: str = "BTC/USDT:USDT",
    store: FeedbackStore | None = None,
    window_days: int = 30,
    min_samples: int = 8,
) -> dict[str, Any]:
    """根据当前 segment 从 Leaderboard 推荐最佳模型。"""
    store = store or FeedbackStore()
    segment = market_context.get("segment_primary") or "global"

    board = store.leaderboard(symbol=symbol, segment=segment, window_days=window_days)
    if not board:
        board = store.leaderboard(symbol=symbol, segment="global", window_days=window_days)

    eligible = [r for r in board if not r.get("low_confidence") and (r.get("sample_count") or 0) >= min_samples]
    if not eligible:
        eligible = [r for r in board if (r.get("sample_count") or 0) > 0]
    if not eligible:
        return {
            "best_model_id": None,
            "best_score": None,
            "segment_primary": segment,
            "alternatives": [],
            "reason": "样本不足，暂无推荐（需更多人工标注与延迟校验）",
            "low_confidence": True,
        }

    eligible.sort(key=lambda x: float(x.get("combined_score") or 0), reverse=True)
    best = eligible[0]
    alts = eligible[1:4]

    return {
        "best_model_id": best["model_id"],
        "best_model_name": MODEL_CATALOG.get(best["model_id"], best["model_id"]),
        "best_score": best["combined_score"],
        "segment_primary": segment,
        "sample_count": best["sample_count"],
        "alternatives": [
            {
                "model_id": a["model_id"],
                "model_name": MODEL_CATALOG.get(a["model_id"], a["model_id"]),
                "combined_score": a["combined_score"],
            }
            for a in alts
        ],
        "reason": (
            f"segment={segment} 近 {window_days} 天 combined={best['combined_score']:.0%} "
            f"(instant={best.get('instant_avg')}, forward={best.get('forward_avg')})"
        ),
        "low_confidence": bool(best.get("low_confidence")),
    }

from __future__ import annotations

from typing import Any

from ai_trade_advisor.regime.feedback.market_context import build_market_context
from ai_trade_advisor.regime.feedback.rollup import refresh_rollup
from ai_trade_advisor.regime.feedback.scoring import score_judgment_instant
from ai_trade_advisor.regime.feedback.store import FeedbackStore
from ai_trade_advisor.regime.judgment_store import HumanJudgmentStore


def record_human_judgment_with_scoring(
    symbol: str,
    *,
    human_regime: str,
    human_trend: str | None = None,
    human_notes: str | None = None,
    btc_regime: dict[str, Any] | None = None,
    advice: dict[str, Any] | None = None,
    board_regime: str | None = None,
    as_of: str | None = None,
    judgment_store: HumanJudgmentStore | None = None,
    feedback_store: FeedbackStore | None = None,
) -> dict[str, Any]:
    """入库人工标注 + 固化市场上下文 + 即时打分（含 LLM/规则建议）。"""
    judgment_store = judgment_store or HumanJudgmentStore()
    feedback_store = feedback_store or FeedbackStore()

    btc = btc_regime or {}
    market_context = build_market_context(btc)
    model_predictions: dict[str, Any] = {
        "models": btc.get("models"),
        "comparison": btc.get("model_comparison"),
    }
    if advice:
        model_predictions["advice"] = advice
        if board_regime:
            model_predictions["board_regime"] = board_regime

    row_id = judgment_store.record(
        symbol,
        human_regime=human_regime,
        human_trend=human_trend,
        human_notes=human_notes,
        model_predictions=model_predictions,
        bar_close=btc.get("close"),
        market_context=market_context,
        bar_timestamp=market_context.get("bar_timestamp") or as_of,
        as_of=as_of,
    )

    judgment = judgment_store.get_by_id(row_id)
    if judgment is None:
        return {"id": row_id, "scores": {}}

    instant_scores = score_judgment_instant(judgment)
    feedback_store.save_scores(instant_scores)
    refresh_rollup(feedback_store, symbol=symbol)

    scores_map = {s["model_id"]: s["total_score"] for s in instant_scores}
    return {"id": row_id, "scores": scores_map, "instant_scores": instant_scores}

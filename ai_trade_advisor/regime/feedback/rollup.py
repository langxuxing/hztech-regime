from __future__ import annotations

from typing import Any

from ai_trade_advisor.regime.feedback.store import FeedbackStore
from ai_trade_advisor.regime.models.base import MODEL_CATALOG


def refresh_rollup(
    store: FeedbackStore | None = None,
    *,
    symbol: str = "",
    window_days: int = 30,
    min_samples: int = 8,
) -> list[dict[str, Any]]:
    """按 segment x model 聚合 instant/forward 分数。"""
    store = store or FeedbackStore()
    rows = store.scores_joined_recent(symbol=symbol, window_days=window_days)

    buckets: dict[tuple[str, str, str], dict[str, list[float]]] = {}
    for r in rows:
        key = (r["symbol"], r["segment_primary"], r["model_id"])
        if key not in buckets:
            buckets[key] = {"instant": [], "forward": []}
        st = r["score_type"]
        if st in buckets[key] and r["total_score"] is not None:
            buckets[key][st].append(float(r["total_score"]))

    rollup_rows: list[dict[str, Any]] = []
    for (sym, seg, model_id), scores in buckets.items():
        instant = scores["instant"]
        forward = scores["forward"]
        instant_avg = sum(instant) / len(instant) if instant else None
        forward_avg = sum(forward) / len(forward) if forward else None
        if instant_avg is not None and forward_avg is not None:
            combined = 0.4 * instant_avg + 0.6 * forward_avg
        elif forward_avg is not None:
            combined = forward_avg
        elif instant_avg is not None:
            combined = instant_avg
        else:
            continue
        count = max(len(instant), len(forward))
        rollup_rows.append(
            {
                "symbol": sym,
                "segment_primary": seg,
                "model_id": model_id,
                "window_days": window_days,
                "sample_count": count,
                "instant_avg": round(instant_avg, 4) if instant_avg is not None else None,
                "forward_avg": round(forward_avg, 4) if forward_avg is not None else None,
                "combined_score": round(combined, 4),
                "low_confidence": count < min_samples,
            }
        )

    # global fallback per symbol+model
    global_buckets: dict[tuple[str, str], dict[str, list[float]]] = {}
    for r in rows:
        key = (r["symbol"], r["model_id"])
        if key not in global_buckets:
            global_buckets[key] = {"instant": [], "forward": []}
        st = r["score_type"]
        if st in global_buckets[key] and r["total_score"] is not None:
            global_buckets[key][st].append(float(r["total_score"]))

    for (sym, model_id), scores in global_buckets.items():
        if any(x["segment_primary"] == "global" and x["model_id"] == model_id for x in rollup_rows):
            continue
        instant = scores["instant"]
        forward = scores["forward"]
        instant_avg = sum(instant) / len(instant) if instant else None
        forward_avg = sum(forward) / len(forward) if forward else None
        if instant_avg is None and forward_avg is None:
            continue
        combined = (
            0.4 * instant_avg + 0.6 * forward_avg
            if instant_avg is not None and forward_avg is not None
            else (forward_avg or instant_avg)
        )
        count = max(len(instant), len(forward))
        rollup_rows.append(
            {
                "symbol": sym,
                "segment_primary": "global",
                "model_id": model_id,
                "window_days": window_days,
                "sample_count": count,
                "instant_avg": round(instant_avg, 4) if instant_avg is not None else None,
                "forward_avg": round(forward_avg, 4) if forward_avg is not None else None,
                "combined_score": round(float(combined), 4),
                "low_confidence": count < min_samples,
            }
        )

    if rollup_rows:
        store.upsert_rollup(rollup_rows)
    return rollup_rows

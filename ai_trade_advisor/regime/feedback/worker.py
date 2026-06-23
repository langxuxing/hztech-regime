from __future__ import annotations

from typing import Any

import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.ohlcv import load_ohlcv
from ai_trade_advisor.regime.feedback.realized import compute_realized_regime, find_bar_index
from ai_trade_advisor.regime.feedback.rollup import refresh_rollup
from ai_trade_advisor.regime.feedback.scoring import score_judgment_forward
from ai_trade_advisor.regime.feedback.store import FeedbackStore


def run_forward_scoring_batch(
    cfg: AdvisorConfig | None = None,
    *,
    store: FeedbackStore | None = None,
) -> dict[str, Any]:
    """扫描待延迟校验的标注并打分。"""
    cfg = cfg or AdvisorConfig.from_env()
    store = store or FeedbackStore()
    forward_bars = cfg.regime_forward_bars
    min_age_minutes = forward_bars * cfg.bar_minutes

    pending = store.pending_forward_judgments(min_age_minutes=min_age_minutes)
    if not pending:
        return {"processed": 0, "errors": []}

    try:
        df = load_ohlcv(cfg)
    except Exception as exc:
        return {"processed": 0, "errors": [str(exc)]}

    processed = 0
    errors: list[str] = []

    for judgment in pending:
        try:
            idx = find_bar_index(
                df,
                bar_close=judgment.get("bar_close"),
                recorded_at=judgment.get("recorded_at"),
            )
            realized = compute_realized_regime(df, idx, forward_bars=forward_bars)
            if realized is None:
                errors.append(f"judgment {judgment['id']}: insufficient bars")
                continue

            scores = score_judgment_forward(judgment, realized)
            store.save_scores(scores)
            store.mark_forward_scored(judgment["id"], realized=realized)
            processed += 1
        except Exception as exc:
            errors.append(f"judgment {judgment['id']}: {exc}")

    refresh_rollup(store, window_days=cfg.regime_rollup_window_days)
    return {"processed": processed, "errors": errors}

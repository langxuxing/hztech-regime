from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from ai_trade_advisor.regime.feedback.realized import find_bar_index
from ai_trade_advisor.regime.feedback.scoring import score_model_against_truth
from ai_trade_advisor.regime.models.base import RegimeModelResult
from ai_trade_advisor.regime.models.clustering import run_clustering_model
from ai_trade_advisor.regime.models.heuristic_advanced import run_heuristic_advanced_model
from ai_trade_advisor.regime.models.hmm_model import run_hmm_model
from ai_trade_advisor.regime.models.hybrid import run_hybrid_model
from ai_trade_advisor.regime.models.msar import run_msar_model


def _result_to_dict(r: RegimeModelResult) -> dict[str, Any]:
    return r.to_dict()


_MODEL_RUNNERS: dict[str, Callable[..., RegimeModelResult]] = {
    "hmm": run_hmm_model,
    "clustering": run_clustering_model,
    "msar": run_msar_model,
    "heuristic_advanced": run_heuristic_advanced_model,
    "hybrid": run_hybrid_model,
}


def replay_param_grid(
    df: pd.DataFrame,
    judgments: list[dict[str, Any]],
    model_id: str,
    param_grid: list[dict[str, Any]],
    *,
    min_bars: int = 80,
) -> tuple[dict[str, Any], float]:
    """在历史 K 线上回放参数网格，以 realized regime 为真值评分。"""
    runner = _MODEL_RUNNERS.get(model_id)
    if runner is None or not param_grid:
        return param_grid[0] if param_grid else {}, 0.0

    best_params = param_grid[0]
    best_score = -1.0

    for params in param_grid:
        scores: list[float] = []
        for j in judgments:
            realized = j.get("realized_regime") or {}
            if not realized.get("realized_trend"):
                continue
            try:
                idx = find_bar_index(
                    df,
                    bar_close=j.get("bar_close"),
                    recorded_at=j.get("recorded_at"),
                )
                if idx + 1 < min_bars:
                    continue
                slice_df = df.iloc[: idx + 1].copy()
                run_params = dict(params)
                if model_id == "hybrid" and "n_states" not in run_params:
                    run_params["n_states"] = 4
                result = runner(slice_df, **run_params)
                if result.error:
                    continue
                scored = score_model_against_truth(
                    _result_to_dict(result),
                    human_regime=realized.get("realized_dashboard") or "range",
                    human_trend=realized.get("realized_trend"),
                    truth_regime=realized.get("realized_dashboard"),
                    truth_trend=realized.get("realized_trend"),
                )
                scores.append(float(scored["total_score"]))
            except Exception:
                continue
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        if avg > best_score:
            best_score = avg
            best_params = params

    return best_params, best_score

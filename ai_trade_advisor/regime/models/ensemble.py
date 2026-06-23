from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from ai_trade_advisor.regime.feedback.params_store import ModelParamsCache
from ai_trade_advisor.regime.models.base import MODEL_CATALOG, RegimeModelResult
from ai_trade_advisor.regime.models.clustering import run_clustering_model
from ai_trade_advisor.regime.models.crypto_lstm import run_crypto_lstm_model
from ai_trade_advisor.regime.models.heuristic import run_heuristic_model
from ai_trade_advisor.regime.models.heuristic_advanced import run_heuristic_advanced_model
from ai_trade_advisor.regime.models.hmm_model import run_hmm_model
from ai_trade_advisor.regime.models.hybrid import run_hybrid_model
from ai_trade_advisor.regime.models.jayd_regime import run_jayd_regime_model
from ai_trade_advisor.regime.models.msar import run_msar_model
from ai_trade_advisor.regime.triad.bocpd import detect_changepoint


def _safe_run(fn, *args, **kwargs) -> RegimeModelResult:
    model_id = kwargs.pop("_model_id", "unknown")
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        return RegimeModelResult(
            model_id=model_id,
            model_name=MODEL_CATALOG.get(model_id, model_id),
            regime_label="模型不可用",
            regime_id=None,
            raw_trend="range",
            vol_bucket="mid_vol",
            dashboard_regime="transition",
            confidence=0.0,
            error=str(exc),
            drivers=[f"错误: {exc}"],
        )


def run_all_regime_models(
    df: pd.DataFrame,
    rule: dict[str, Any],
    *,
    n_hmm_states: int | None = None,
    n_clusters: int | None = None,
    params_cache: ModelParamsCache | None = None,
    segment: str | None = None,
) -> dict[str, Any]:
    """并行运行全部 Regime 模型，供人工对比判断。"""
    import numpy as np

    cache = params_cache or ModelParamsCache.get()
    hmm_p = cache.get_params("hmm")
    cl_p = cache.get_params("clustering")
    msar_p = cache.get_params("msar")
    hybrid_p = cache.get_params("hybrid")
    adv_p = cache.get_params("heuristic_advanced")
    lstm_p = cache.get_params("crypto_lstm")
    jayd_p = cache.get_params("jayd_regime")

    n_hmm = int(n_hmm_states or hmm_p.get("n_states", 4))
    n_cl = int(n_clusters or cl_p.get("n_clusters", 4))
    dtw_w = int(cl_p.get("dtw_window", 24))
    n_msar = int(msar_p.get("n_states", 3))

    results: list[RegimeModelResult] = []

    results.append(_safe_run(run_heuristic_model, rule, _model_id="heuristic"))
    results.append(_safe_run(run_hmm_model, df, n_states=n_hmm, _model_id="hmm"))
    results.append(
        _safe_run(run_clustering_model, df, n_clusters=n_cl, dtw_window=dtw_w, _model_id="clustering")
    )
    results.append(_safe_run(run_msar_model, df, n_states=n_msar, _model_id="msar"))
    results.append(
        _safe_run(
            run_heuristic_advanced_model,
            df,
            adx_trend_threshold=float(adv_p.get("adx_trend_threshold", 28.0)),
            squeeze_overlap_min=float(adv_p.get("squeeze_overlap_min", 0.6)),
            _model_id="heuristic_advanced",
        )
    )
    results.append(
        _safe_run(
            run_hybrid_model,
            df,
            n_states=n_hmm,
            seq_decay=float(hybrid_p.get("seq_decay", 0.85)),
            markov_weight=float(hybrid_p.get("markov_weight", 0.45)),
            seq_weight=float(hybrid_p.get("seq_weight", 0.35)),
            hmm_weight=float(hybrid_p.get("hmm_weight", 0.20)),
            _model_id="hybrid",
        )
    )

    lstm_threshold = float(lstm_p.get("confidence_threshold", 0.5))
    jayd_threshold = float(jayd_p.get("confidence_threshold", 0.5))

    if lstm_p.get("enabled", True):
        lstm_r = _safe_run(run_crypto_lstm_model, df, _model_id="crypto_lstm")
        if lstm_r.error or lstm_r.confidence >= lstm_threshold:
            results.append(lstm_r)
    if jayd_p.get("enabled", True):
        jayd_r = _safe_run(run_jayd_regime_model, df, _model_id="jayd_regime")
        if jayd_r.error or jayd_r.confidence >= jayd_threshold:
            results.append(jayd_r)

    changepoint_prob: float | None = None
    hazard = float(hmm_p.get("hazard_lambda", 80.0))
    try:
        close = df["close"].astype(float)
        ret = np.log(close / close.shift(1)).dropna().to_numpy()
        bocpd = detect_changepoint(ret, hazard_lambda=hazard)
        changepoint_prob = round(bocpd.changepoint_prob, 4)
    except Exception:
        pass

    weights = cache.ensemble_weights(segment)
    trends_weighted: Counter[str] = Counter()
    for r in results:
        if r.error:
            continue
        w = float(weights.get(r.model_id, 1.0))
        trends_weighted[r.raw_trend] += w

    if trends_weighted:
        dominant_trend = trends_weighted.most_common(1)[0][0]
        trend_count = trends_weighted[dominant_trend]
        agreement = trend_count / sum(trends_weighted.values())
    else:
        dominant_trend, agreement = "range", 0.0

    dashboards = [r.dashboard_regime for r in results if not r.error]
    dash_votes = Counter(dashboards)
    dominant_dashboard = dash_votes.most_common(1)[0][0] if dash_votes else "transition"

    disagreement_models = [
        r.model_id for r in results if not r.error and r.raw_trend != dominant_trend
    ]

    comparison = {
        "dominant_trend": dominant_trend,
        "dominant_dashboard": dominant_dashboard,
        "agreement_ratio": round(agreement, 4),
        "disagreement_models": disagreement_models,
        "changepoint_prob": changepoint_prob,
        "model_count": len(results),
        "needs_human_judgment": agreement < 0.67 or len(disagreement_models) >= 3,
        "summary": _comparison_summary(results, dominant_trend, agreement, disagreement_models),
        "params_version": cache.active_versions(),
    }

    return {
        "models": {r.model_id: r.to_dict() for r in results},
        "comparison": comparison,
    }


def _comparison_summary(
    results: list[RegimeModelResult],
    dominant_trend: str,
    agreement: float,
    disagreement_models: list[str],
) -> str:
    lines = [f"多模型对比：{len(results)} 个模型，趋势共识 {dominant_trend} ({agreement:.0%})"]
    for r in results:
        if r.error:
            lines.append(f"  · {r.model_id}: 失败")
        else:
            lines.append(f"  · {r.model_id}: {r.regime_label} ({r.confidence:.0%})")
    if disagreement_models:
        lines.append(f"分歧模型: {', '.join(disagreement_models)} → 建议人工判断")
    return " ".join(lines[:4]) + (" …" if len(lines) > 4 else "")

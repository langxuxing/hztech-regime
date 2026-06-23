from __future__ import annotations

import pandas as pd

from algorithm.hybrid import fit_hybrid_regime
from ai_trade_advisor.regime.models.base import MODEL_CATALOG, RegimeModelResult, trend_to_dashboard


def run_hybrid_model(
    df: pd.DataFrame,
    *,
    n_states: int = 4,
    seq_decay: float = 0.85,
    markov_weight: float = 0.45,
    seq_weight: float = 0.35,
    hmm_weight: float = 0.20,
) -> RegimeModelResult:
    result = fit_hybrid_regime(
        df,
        n_states=n_states,
        seq_decay=seq_decay,
        markov_weight=markov_weight,
        seq_weight=seq_weight,
        hmm_weight=hmm_weight,
    )
    label_cn = {
        "bull": "组合 · 低波上涨",
        "bear": "组合 · 高波下跌",
        "range": "组合 · 震荡",
        "crisis": "组合 · 危机波动",
    }
    return RegimeModelResult(
        model_id="hybrid",
        model_name=MODEL_CATALOG["hybrid"],
        regime_label=f"Hybrid · {label_cn.get(result.pred_label, result.pred_label)}",
        regime_id=f"hybrid_{result.pred_label}",
        raw_trend=result.raw_trend,
        vol_bucket=result.vol_bucket,
        dashboard_regime=trend_to_dashboard(result.raw_trend, result.vol_bucket),
        confidence=result.confidence,
        state_probs=result.state_probs,
        next_regime_label=result.next_regime_label,
        drivers=result.drivers,
        metadata=result.metadata,
        error=result.error,
    )

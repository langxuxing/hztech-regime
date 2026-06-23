from __future__ import annotations

import pandas as pd

from algorithm.heuristic import fit_heuristic_regime
from ai_trade_advisor.regime.models.base import MODEL_CATALOG, RegimeModelResult, trend_to_dashboard


def run_heuristic_advanced_model(
    df: pd.DataFrame,
    *,
    adx_trend_threshold: float = 28.0,
    squeeze_overlap_min: float = 0.6,
) -> RegimeModelResult:
    result = fit_heuristic_regime(
        df,
        adx_trend_threshold=adx_trend_threshold,
        squeeze_overlap_min=squeeze_overlap_min,
    )
    return RegimeModelResult(
        model_id="heuristic_advanced",
        model_name=MODEL_CATALOG["heuristic_advanced"],
        regime_label=result.regime_label,
        regime_id=result.regime_id,
        raw_trend=result.raw_trend,
        vol_bucket=result.vol_bucket,
        dashboard_regime=trend_to_dashboard(result.raw_trend, result.vol_bucket),
        confidence=result.confidence,
        drivers=result.drivers,
        metadata=result.metadata,
    )

from __future__ import annotations

import pandas as pd

from ai_trade_advisor.regime.engines.jayd_analysis import analyze_jayd_regime
from ai_trade_advisor.regime.models.base import MODEL_CATALOG, RegimeModelResult, trend_to_dashboard


def run_jayd_regime_model(df: pd.DataFrame) -> RegimeModelResult:
    """Market-Regime-Modeling-and-Rates-Prediction-Analysis (jayd-bit) DT+HMM 引擎。"""
    analysis = analyze_jayd_regime(df)

    combined_label = f"Jayd · {analysis.dt_regime} / {analysis.hmm_state}"
    regime_id = f"jayd_{analysis.dt_regime.lower().replace(' ', '_')}"

    confidence = (analysis.dt_confidence + analysis.hmm_confidence) / 2.0

    return RegimeModelResult(
        model_id="jayd_regime",
        model_name=MODEL_CATALOG["jayd_regime"],
        regime_label=combined_label,
        regime_id=regime_id,
        raw_trend=analysis.raw_trend,
        vol_bucket=analysis.vol_bucket,
        dashboard_regime=trend_to_dashboard(analysis.raw_trend, analysis.vol_bucket),
        confidence=confidence,
        state_probs=analysis.state_probs,
        next_regime_label=analysis.next_regime_label,
        drivers=analysis.drivers,
        metadata={
            **(analysis.metadata or {}),
            "dt_regime": analysis.dt_regime,
            "dt_confidence": analysis.dt_confidence,
            "hmm_state": analysis.hmm_state,
            "hmm_confidence": analysis.hmm_confidence,
            "transition_matrix": analysis.transition_matrix,
        },
        error=analysis.error,
    )

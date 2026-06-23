from __future__ import annotations

import pandas as pd

from algorithm.msar import fit_msar_regime
from ai_trade_advisor.regime.models.base import MODEL_CATALOG, RegimeModelResult, trend_to_dashboard


def run_msar_model(df: pd.DataFrame, *, n_states: int = 3) -> RegimeModelResult:
    result = fit_msar_regime(df, n_states=n_states)
    label_cn = {
        "bull": "MS-AR · 低波上涨态",
        "bear": "MS-AR · 高波下跌态",
        "range": "MS-AR · 震荡态",
        "crisis": "MS-AR · 危机态",
    }
    return RegimeModelResult(
        model_id="msar",
        model_name=MODEL_CATALOG["msar"],
        regime_label=label_cn.get(result.label, result.label),
        regime_id=f"msar_{result.label}",
        raw_trend=result.raw_trend,
        vol_bucket=result.vol_bucket,
        dashboard_regime=trend_to_dashboard(result.raw_trend, result.vol_bucket),
        confidence=result.confidence,
        state_probs=result.state_probs,
        next_regime_label=result.next_label,
        drivers=result.drivers,
        metadata={**result.metadata, "backend": result.backend},
    )

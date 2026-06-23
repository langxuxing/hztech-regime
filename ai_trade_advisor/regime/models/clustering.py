from __future__ import annotations

import pandas as pd

from algorithm.clustering import fit_clustering_regime
from ai_trade_advisor.regime.models.base import MODEL_CATALOG, RegimeModelResult, trend_to_dashboard


def run_clustering_model(df: pd.DataFrame, *, n_clusters: int = 4, dtw_window: int = 24) -> RegimeModelResult:
    result = fit_clustering_regime(df, n_clusters=n_clusters, dtw_window=dtw_window)
    label_map = {
        "bull": "聚类 · 低波动上涨簇",
        "bear": "聚类 · 高波动下跌簇",
        "range": "聚类 · 震荡簇",
        "crisis": "聚类 · 极端波动簇",
    }
    return RegimeModelResult(
        model_id="clustering",
        model_name=MODEL_CATALOG["clustering"],
        regime_label=label_map.get(result.sem_label, result.sem_label),
        regime_id=f"cluster_{result.sem_label}",
        raw_trend=result.raw_trend,
        vol_bucket=result.vol_bucket,
        dashboard_regime=trend_to_dashboard(result.raw_trend, result.vol_bucket),
        confidence=result.confidence,
        state_probs=result.state_probs,
        drivers=result.drivers,
        metadata=result.metadata,
    )

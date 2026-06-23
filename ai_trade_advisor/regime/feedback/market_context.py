from __future__ import annotations

from typing import Any

import pandas as pd

from algorithm.heuristic import fit_heuristic_regime
from ai_trade_advisor.regime.matrix import _cell_from_axes


def build_market_context(btc_regime: dict[str, Any], *, df: pd.DataFrame | None = None) -> dict[str, Any]:
    """标注时刻固化市场上下文，供分市场 Leaderboard 与调参使用。"""
    raw_trend = btc_regime.get("raw_trend")
    vol_bucket = btc_regime.get("vol_bucket")
    regime_id = btc_regime.get("regime_id") or ""
    dashboard = btc_regime.get("dashboard_regime") or "transition"

    if regime_id == "macro_frozen_range":
        segment_primary = "macro_frozen"
    elif btc_regime.get("in_regime_transition") or dashboard == "transition":
        segment_primary = "transition"
    else:
        segment_primary = regime_id or _cell_from_axes(raw_trend, vol_bucket)

    comparison = btc_regime.get("model_comparison") or {}
    changepoint_prob = btc_regime.get("changepoint_prob") or comparison.get("changepoint_prob")

    features: dict[str, Any] = {
        "vol_bucket": vol_bucket,
        "raw_trend": raw_trend,
        "changepoint_prob": changepoint_prob,
    }

    if df is not None and len(df) >= 50:
        try:
            adv = fit_heuristic_regime(df)
            meta = adv.metadata or {}
            features["adx"] = meta.get("adx")
            features["squeeze"] = meta.get("squeeze")
            features["squeeze_overlap"] = meta.get("squeeze_overlap")
        except Exception:
            pass
    else:
        models = btc_regime.get("models") or {}
        adv = models.get("heuristic_advanced") or {}
        meta = adv.get("metadata") or {}
        if meta:
            features["adx"] = meta.get("adx")
            features["squeeze"] = meta.get("squeeze")
            features["squeeze_overlap"] = meta.get("squeeze_overlap")

    return {
        "segment_primary": segment_primary,
        "segment_features": features,
        "close": btc_regime.get("close"),
        "bar_timestamp": btc_regime.get("as_of"),
        "dashboard_regime": dashboard,
        "regime_id": regime_id,
    }

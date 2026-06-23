from __future__ import annotations

import pandas as pd

from ai_trade_advisor.regime.engines.akash_lstm import predict_akash_regime
from ai_trade_advisor.regime.models.base import MODEL_CATALOG, RegimeModelResult, trend_to_dashboard


def run_crypto_lstm_model(df: pd.DataFrame) -> RegimeModelResult:
    """CryptoMarket_Regime_Classifier (akash-kumar5) LSTM/HMM Regime 预测引擎。"""
    pred = predict_akash_regime(df)

    engine = (pred.metadata or {}).get("engine", "akash_lstm")
    prefix = "LSTM" if engine == "akash_lstm" else "HMM"
    label = f"{prefix} · {pred.regime}" if pred.regime != "Unknown" else f"{prefix} · 不可用"
    regime_id = f"lstm_{pred.regime.lower().replace(' ', '_')}" if pred.regime != "Unknown" else None

    return RegimeModelResult(
        model_id="crypto_lstm",
        model_name=MODEL_CATALOG["crypto_lstm"],
        regime_label=label,
        regime_id=regime_id,
        raw_trend=pred.raw_trend,
        vol_bucket=pred.vol_bucket,
        dashboard_regime=trend_to_dashboard(pred.raw_trend, pred.vol_bucket),
        confidence=pred.confidence,
        state_probs=pred.probs or None,
        next_regime_label=pred.next_regime_label,
        drivers=pred.drivers,
        metadata=pred.metadata,
        error=pred.error,
    )

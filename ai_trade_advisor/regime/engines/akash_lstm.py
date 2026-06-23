from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import joblib
import numpy as np
import pandas as pd

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.regime.engines.akash_features import build_akash_features
from ai_trade_advisor.regime.engines.btc_multiframe import prepare_btc_multiframe
from ai_trade_advisor.regime.engines.vendor_paths import (
    AKASH_HMM_BUNDLE,
    AKASH_LSTM_MODEL,
    AKASH_METADATA,
    AKASH_MODEL_DIR,
    AKASH_SCALER,
    AKASH_VENDOR,
)

REGIME_TREND_MAP: dict[str, tuple[str, str]] = {
    "Strong Trend": ("uptrend", "low_vol"),
    "Weak Trend": ("uptrend", "mid_vol"),
    "Range": ("range", "mid_vol"),
    "Squeeze": ("range", "low_vol"),
    "Choppy High-Vol": ("range", "high_vol"),
    "Volatility Spike": ("downtrend", "high_vol"),
}


@dataclass
class AkashRegimePrediction:
    regime: str
    confidence: float
    probs: dict[str, float]
    raw_trend: str
    vol_bucket: str
    next_regime_label: str | None = None
    drivers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _load_metadata() -> dict[str, Any]:
    if not AKASH_METADATA.exists():
        raise FileNotFoundError(f"akash metadata not found: {AKASH_METADATA}")
    with open(AKASH_METADATA, encoding="utf-8") as f:
        return json.load(f)


def _load_scaler():
    if not AKASH_SCALER.exists():
        raise FileNotFoundError(f"akash scaler not found: {AKASH_SCALER}")
    return joblib.load(AKASH_SCALER)


def _load_lstm_model():
    if not AKASH_LSTM_MODEL.exists():
        raise FileNotFoundError(f"akash LSTM model not found: {AKASH_LSTM_MODEL}")
    try:
        from tensorflow.keras.models import load_model
    except ImportError as exc:
        raise ImportError(
            "tensorflow is required for CryptoMarket_Regime_Classifier LSTM engine; "
            "install with: pip install tensorflow"
        ) from exc
    return load_model(AKASH_LSTM_MODEL)


def _forecast_next_regime(probs: dict[str, float]) -> str | None:
    if not probs:
        return None
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    if len(ranked) < 2:
        return ranked[0][0]
    return ranked[1][0]


def _load_hmm_bundle():
    if not AKASH_HMM_BUNDLE or not AKASH_HMM_BUNDLE.exists():
        raise FileNotFoundError(f"akash HMM bundle not found under {AKASH_MODEL_DIR}")
    return joblib.load(AKASH_HMM_BUNDLE)


def _predict_hmm_fallback(
    features: pd.DataFrame,
    *,
    bundle: dict,
) -> AkashRegimePrediction:
    """TensorFlow 不可用时，使用 vendor 预训练 6-state HMM。"""
    hmm_model = bundle["hmm_model"]
    scaler = bundle["scaler"]
    pca = bundle["pca"]
    feature_list = bundle["features"]
    state_mapping = {int(k): v for k, v in bundle["state_mapping"].items()}

    missing = [c for c in feature_list if c not in features.columns]
    if missing:
        raise ValueError(f"missing HMM features: {missing}")

    feat = features[feature_list].dropna()
    if len(feat) < 30:
        raise ValueError("insufficient rows for HMM inference")

    x = scaler.transform(feat)
    x = pca.transform(x)
    states = hmm_model.predict(x)
    post = hmm_model.predict_proba(x)[-1]
    state = int(states[-1])
    regime = state_mapping.get(state, f"State_{state}")
    confidence = float(post[state])

    probs = {
        state_mapping.get(i, f"State_{i}"): float(post[i])
        for i in range(len(post))
    }
    raw_trend, vol_bucket = REGIME_TREND_MAP.get(regime, ("range", "mid_vol"))
    next_label = _forecast_next_regime(probs)

    trans = hmm_model.transmat_
    next_state = int(np.argmax(trans[state]))
    trans_next = state_mapping.get(next_state)

    drivers = [
        f"HMM(6) · {regime} ({confidence:.0%}) [LSTM fallback]",
        f"预训练 bundle: {AKASH_HMM_BUNDLE.name}",
        f"vendor: CryptoMarket_Regime_Classifier",
    ]
    if trans_next and trans_next != regime:
        drivers.append(f"转移矩阵下一状态: {trans_next}")

    return AkashRegimePrediction(
        regime=regime,
        confidence=confidence,
        probs=probs,
        raw_trend=raw_trend,
        vol_bucket=vol_bucket,
        next_regime_label=next_label or trans_next,
        drivers=drivers,
        metadata={
            "engine": "akash_hmm_fallback",
            "bundle": str(AKASH_HMM_BUNDLE),
            "n_states": bundle.get("n_states", 6),
        },
    )


def predict_akash_regime(
    df: pd.DataFrame | None = None,
    *,
    cfg: AdvisorConfig | None = None,
) -> AkashRegimePrediction:
    """
    使用 vendor/CryptoMarket_Regime_Classifier 预训练 LSTM 对 BTC 进行 Regime 预测。
    数据源：项目 OHLCV 或 ccxt 拉取 5m/15m。
    """
    if not AKASH_VENDOR.exists():
        return AkashRegimePrediction(
            regime="Unknown",
            confidence=0.0,
            probs={},
            raw_trend="range",
            vol_bucket="mid_vol",
            error=f"vendor repo missing: {AKASH_VENDOR}",
        )

    try:
        metadata = _load_metadata()
        feature_columns = metadata["features"]
        time_steps = int(metadata.get("time_steps", 64))
        regime_map = {int(v): k for k, v in metadata["regime_map"].items()}

        bundle = prepare_btc_multiframe(df, cfg=cfg, main_tf="5m", context_tfs=["15m"], limit=500)
        features = build_akash_features(
            bundle["merged"],
            main_tf=bundle["main_tf"],
            context_tfs=bundle["context_tfs"],
        )

        missing = [c for c in feature_columns if c not in features.columns]
        if missing:
            raise ValueError(f"missing akash features: {missing}")

        if len(features) < time_steps:
            raise ValueError(f"need at least {time_steps} feature rows, got {len(features)}")

        window = features[feature_columns].tail(time_steps)
        if window.isna().any().any():
            raise ValueError("NaN in feature window")

        scaler = _load_scaler()
        model = _load_lstm_model()
        scaled = scaler.transform(window)
        batch = np.expand_dims(scaled, axis=0)
        probabilities = model.predict(batch, verbose=0)[0]

        class_index = int(np.argmax(probabilities))
        predicted_regime = regime_map.get(class_index, "Unknown")
        confidence = float(probabilities[class_index])
        probs = {
            regime_map[int(class_id)]: float(probabilities[int(class_id)])
            for class_id in metadata["regime_map"].values()
            if int(class_id) < len(probabilities)
        }

        raw_trend, vol_bucket = REGIME_TREND_MAP.get(predicted_regime, ("range", "mid_vol"))
        next_label = _forecast_next_regime(probs)

        drivers = [
            f"LSTM · {predicted_regime} ({confidence:.0%})",
            f"数据源: BTC 5m/15m ({len(features)} bars)",
            f"vendor: CryptoMarket_Regime_Classifier",
        ]
        if next_label and next_label != predicted_regime:
            drivers.append(f"次高概率 Regime: {next_label} ({probs.get(next_label, 0):.0%})")

        return AkashRegimePrediction(
            regime=predicted_regime,
            confidence=confidence,
            probs=probs,
            raw_trend=raw_trend,
            vol_bucket=vol_bucket,
            next_regime_label=next_label,
            drivers=drivers,
            metadata={
                "engine": "akash_lstm",
                "time_steps": time_steps,
                "feature_count": len(feature_columns),
                "vendor": str(AKASH_VENDOR),
            },
        )
    except ImportError:
        try:
            bundle = _load_hmm_bundle()
            return _predict_hmm_fallback(features, bundle=bundle)
        except Exception as inner:
            return AkashRegimePrediction(
                regime="Unknown",
                confidence=0.0,
                probs={},
                raw_trend="range",
                vol_bucket="mid_vol",
                error=str(inner),
                drivers=[f"akash HMM fallback 失败: {inner}"],
            )
    except Exception as exc:
        return AkashRegimePrediction(
            regime="Unknown",
            confidence=0.0,
            probs={},
            raw_trend="range",
            vol_bucket="mid_vol",
            error=str(exc),
            drivers=[f"akash LSTM 失败: {exc}"],
        )

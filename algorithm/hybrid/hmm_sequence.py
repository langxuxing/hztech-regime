from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from algorithm.common.features import build_regime_features
from algorithm.hmm.gaussian_hmm import fit_hmm_regime, forecast_transition


@dataclass
class HybridRegimeResult:
    hmm_label: str
    pred_label: str
    raw_trend: str
    vol_bucket: str
    confidence: float
    state_probs: dict[str, float]
    next_regime_label: str
    transition_label: str
    drivers: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    error: str | None = None


def _sequence_momentum(state_seq: np.ndarray, n_states: int, *, decay: float = 0.85) -> np.ndarray:
    weights = np.array([decay ** i for i in range(len(state_seq))][::-1])
    weights /= weights.sum() + 1e-12
    agg = np.zeros(n_states)
    for w, s in zip(weights, state_seq):
        agg[int(s)] += w
    return agg / (agg.sum() + 1e-12)


def fit_hybrid_regime(
    df: pd.DataFrame,
    *,
    n_states: int = 4,
    seq_decay: float = 0.85,
    markov_weight: float = 0.45,
    seq_weight: float = 0.35,
    hmm_weight: float = 0.20,
) -> HybridRegimeResult:
    """HMM 无监督标注 + 马尔可夫转移 + 序列加权预测 (LSTM 轻量替代)。"""
    hmm, trans, state_labels = fit_hmm_regime(df, n_states=n_states)
    transition = forecast_transition(hmm, trans, state_labels, horizon=3)

    x = build_regime_features(df)
    state_seq: np.ndarray
    try:
        from hmmlearn.hmm import GaussianHMM

        model = GaussianHMM(n_components=n_states, covariance_type="diag", n_iter=80, random_state=42)
        model.fit(x)
        state_seq = model.predict(x)
    except Exception:
        ret = x[:, 0]
        q = np.quantile(ret, np.linspace(0, 1, n_states + 1))
        state_seq = np.clip(np.digitize(ret, q[1:-1]), 0, n_states - 1)

    seq_probs = _sequence_momentum(state_seq[-24:], n_states, decay=seq_decay)
    markov_probs = np.array(hmm.state_probs) @ trans
    blended = markov_weight * markov_probs + seq_weight * seq_probs + hmm_weight * np.array(hmm.state_probs)
    blended /= blended.sum() + 1e-12
    pred_idx = int(np.argmax(blended))
    pred_label = state_labels[pred_idx] if pred_idx < len(state_labels) else "range"
    conf = float(blended[pred_idx])

    trend_map = {"bull": "uptrend", "bear": "downtrend", "crisis": "downtrend"}
    vol_map = {"crisis": "high_vol", "bear": "mid_vol", "bull": "low_vol"}
    raw_trend = trend_map.get(hmm.current_label, "range")
    vol_bucket = vol_map.get(hmm.current_label, "mid_vol")

    drivers = [
        f"HMM 标注: {hmm.current_label}",
        f"序列动量 → {pred_label} (conf {conf:.0%})",
        transition.label,
        "HMM 无监督标注 + 马尔可夫转移 + 序列加权预测",
    ]
    state_probs = {
        state_labels[i]: round(float(blended[i]), 4)
        for i in range(min(len(state_labels), len(blended)))
    }

    return HybridRegimeResult(
        hmm_label=hmm.current_label,
        pred_label=pred_label,
        raw_trend=raw_trend,
        vol_bucket=vol_bucket,
        confidence=conf,
        state_probs=state_probs,
        next_regime_label=pred_label,
        transition_label=transition.label,
        drivers=drivers,
        metadata={
            "hmm_state": hmm.current_label,
            "sequence_pred": pred_label,
            "transition": transition.to_dict(),
        },
        error=hmm.error,
    )

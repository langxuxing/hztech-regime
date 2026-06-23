from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from algorithm.common.features import build_regime_features

HMM_STATE_LABELS = ("bear", "range", "bull", "crisis")


@dataclass
class HmmRegimeResult:
    n_states: int
    current_state: int
    current_label: str
    state_probs: list[float]
    state_labels: list[str]
    raw_trend_hint: str
    vol_hint: str
    confidence: float
    model: str = "gaussian_hmm"
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "n_states": self.n_states,
            "current_state": self.current_state,
            "current_label": self.current_label,
            "state_probs": [round(p, 4) for p in self.state_probs],
            "state_labels": self.state_labels,
            "raw_trend_hint": self.raw_trend_hint,
            "vol_hint": self.vol_hint,
            "confidence": round(self.confidence, 4),
            "model": self.model,
            "error": self.error,
        }


@dataclass
class TransitionForecast:
    horizon_bars: int
    next_label: str
    next_probs: dict[str, float]
    persistence: float
    switch_risk: float
    label: str

    def to_dict(self) -> dict:
        return {
            "horizon_bars": self.horizon_bars,
            "next_label": self.next_label,
            "next_probs": {k: round(v, 4) for k, v in self.next_probs.items()},
            "persistence": round(self.persistence, 4),
            "switch_risk": round(self.switch_risk, 4),
            "label": self.label,
        }


def _label_states(means: np.ndarray, covars: np.ndarray) -> list[str]:
    n = means.shape[0]
    ret_mu = means[:, 0]
    vol_mu = means[:, 1] if means.shape[1] > 1 else np.zeros(n)
    order = np.argsort(ret_mu)
    labels = [""] * n
    if n <= 3:
        names = ["bear", "range", "bull"][:n]
        for i, idx in enumerate(order):
            labels[idx] = names[min(i, len(names) - 1)]
        return labels

    crisis_idx = int(np.argmax(vol_mu))
    labels[crisis_idx] = "crisis"
    remaining = [i for i in range(n) if i != crisis_idx]
    remaining.sort(key=lambda i: ret_mu[i])
    names_cycle = ["bear", "range", "bull"]
    for j, idx in enumerate(remaining):
        labels[idx] = names_cycle[min(j, len(names_cycle) - 1)]
    return labels


def _fit_fallback_hmm(x: np.ndarray, n_states: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    ret = x[:, 0]
    q = np.quantile(ret, np.linspace(0, 1, n_states + 1))
    states = np.clip(np.digitize(ret, q[1:-1]), 0, n_states - 1)
    trans = np.full((n_states, n_states), 1.0 / n_states)
    for t in range(1, len(states)):
        i, j = int(states[t - 1]), int(states[t])
        trans[i, j] += 1.0
    trans = trans / (trans.sum(axis=1, keepdims=True) + 1e-8)
    means = np.zeros((n_states, x.shape[1]))
    covars = np.ones((n_states, x.shape[1]))
    for s in range(n_states):
        mask = states == s
        if mask.any():
            means[s] = x[mask].mean(axis=0)
            covars[s] = x[mask].var(axis=0) + 1e-6
    return trans, means, covars, "quantile_fallback"


def fit_hmm_regime(df: pd.DataFrame, *, n_states: int = 4) -> tuple[HmmRegimeResult, np.ndarray, list[str]]:
    """Gaussian HMM (hmmlearn) 拟合 BTC Regime，失败时降级为分位分桶。"""
    x = build_regime_features(df)
    model_name = "quantile_fallback"
    trans: np.ndarray
    means: np.ndarray
    covars: np.ndarray
    probs: np.ndarray

    try:
        from hmmlearn.hmm import GaussianHMM

        best_model: GaussianHMM | None = None
        best_bic = np.inf
        for seed in (42, 7, 13):
            model = GaussianHMM(
                n_components=n_states,
                covariance_type="diag",
                n_iter=120,
                random_state=seed,
                tol=1e-3,
            )
            model.fit(x)
            n, d = x.shape
            k = n_states * (n_states - 1) + n_states * d + n_states * d
            ll = model.score(x)
            bic = -2.0 * ll + k * np.log(max(n, 1))
            if bic < best_bic:
                best_bic = bic
                best_model = model
        if best_model is None:
            raise RuntimeError("hmm fit failed")
        trans = best_model.transmat_
        means = best_model.means_
        covars = best_model.covars_
        _, post = best_model.score_samples(x)
        probs = post[-1]
        current = int(np.argmax(probs))
        model_name = "gaussian_hmm"
    except Exception:
        trans, means, covars, model_name = _fit_fallback_hmm(x, n_states)
        ret_last = x[-1, 0]
        q = np.quantile(x[:, 0], np.linspace(0, 1, n_states + 1))
        current = int(np.clip(np.digitize(ret_last, q[1:-1]), 0, n_states - 1))
        probs = np.zeros(n_states)
        probs[current] = 1.0

    state_labels = _label_states(means, covars)
    label = state_labels[current]
    conf = float(probs[current])
    trend_hint = {"bull": "uptrend", "bear": "downtrend", "crisis": "downtrend"}.get(label, "range")
    vol_hint = "high_vol" if label == "crisis" else "mid_vol" if label == "range" else "low_vol"

    result = HmmRegimeResult(
        n_states=n_states,
        current_state=current,
        current_label=label,
        state_probs=[float(p) for p in probs],
        state_labels=state_labels,
        raw_trend_hint=trend_hint,
        vol_hint=vol_hint,
        confidence=conf,
        model=model_name,
    )
    return result, trans, state_labels


def forecast_transition(
    hmm: HmmRegimeResult,
    trans: np.ndarray,
    state_labels: list[str],
    *,
    horizon: int = 3,
) -> TransitionForecast:
    probs = np.array(hmm.state_probs, dtype=float)
    probs = probs / (probs.sum() + 1e-12)
    tm = np.linalg.matrix_power(trans, horizon)
    next_probs_vec = probs @ tm

    agg: dict[str, float] = {lab: 0.0 for lab in HMM_STATE_LABELS}
    for i, p in enumerate(next_probs_vec):
        lab = state_labels[i] if i < len(state_labels) else "range"
        agg[lab] = agg.get(lab, 0.0) + float(p)

    next_label = max(agg, key=agg.get)  # type: ignore[arg-type]
    persistence = float(probs @ np.diag(trans))
    switch_risk = float(1.0 - persistence)

    label = (
        f"{horizon}bar 后最可能 → {next_label} "
        f"(维持当前 {persistence:.0%} / 切换风险 {switch_risk:.0%})"
    )
    return TransitionForecast(
        horizon_bars=horizon,
        next_label=next_label,
        next_probs=agg,
        persistence=persistence,
        switch_risk=switch_risk,
        label=label,
    )

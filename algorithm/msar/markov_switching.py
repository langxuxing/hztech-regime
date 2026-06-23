from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class MsarRegimeResult:
    label: str
    raw_trend: str
    vol_bucket: str
    confidence: float
    next_label: str
    state_probs: dict[str, float]
    drivers: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    backend: str = "builtin_em"


def _fit_msar_em(returns: np.ndarray, *, n_states: int = 3, max_iter: int = 25) -> dict:
    r = returns.astype(float)
    if len(r) < 40:
        raise ValueError("insufficient returns for MS-AR")

    vol = pd.Series(r).rolling(6, min_periods=3).std().bfill().to_numpy()
    q = np.quantile(vol, np.linspace(0, 1, n_states + 1))
    states = np.clip(np.digitize(vol, q[1:-1]), 0, n_states - 1)

    trans = np.full((n_states, n_states), 1.0 / n_states)
    mus = np.zeros(n_states)
    phis = np.zeros(n_states)
    sigmas = np.ones(n_states) * 0.01

    for _ in range(max_iter):
        for s in range(n_states):
            mask = states == s
            if mask.sum() < 3:
                continue
            y = r[1:][mask[1:]]
            x = r[:-1][mask[1:]]
            if len(y) < 2:
                continue
            phi = np.cov(y, x)[0, 1] / (np.var(x) + 1e-8)
            phi = float(np.clip(phi, -0.95, 0.95))
            mu = float(y.mean() - phi * x.mean())
            resid = y - mu - phi * x
            sigmas[s] = float(np.std(resid) + 1e-6)
            mus[s], phis[s] = mu, phi

        new_states = np.zeros(len(r), dtype=int)
        for t in range(1, len(r)):
            scores = []
            for s in range(n_states):
                pred = mus[s] + phis[s] * r[t - 1]
                ll = -0.5 * ((r[t] - pred) / sigmas[s]) ** 2 - np.log(sigmas[s])
                scores.append(ll)
            new_states[t] = int(np.argmax(scores))
        states = new_states

        for i in range(n_states):
            for j in range(n_states):
                trans[i, j] = 1.0
        for t in range(1, len(states)):
            trans[int(states[t - 1]), int(states[t])] += 1.0
        trans = trans / (trans.sum(axis=1, keepdims=True) + 1e-8)

    current = int(states[-1])
    probs = np.zeros(n_states)
    probs[current] = 1.0
    next_probs = probs @ trans
    return {
        "current": current,
        "probs": probs,
        "next_probs": next_probs,
        "trans": trans,
        "mus": mus,
        "phis": phis,
        "sigmas": sigmas,
        "states": states,
    }


def _fit_statsmodels_msar(returns: np.ndarray, *, n_states: int = 3) -> dict | None:
    """statsmodels MarkovAutoregression，可用时优先使用。"""
    try:
        from statsmodels.tsa.regime_switching.markov_autoregression import MarkovAutoregression

        model = MarkovAutoregression(returns, k_regimes=n_states, order=1, switching_ar=True)
        result = model.fit(disp=False, maxiter=50)

        smp = result.smoothed_marginal_probabilities
        if hasattr(smp, "iloc"):
            probs = smp.iloc[-1].to_numpy(dtype=float)
            states = smp.idxmax(axis=1).to_numpy()
        else:
            smp_arr = np.asarray(smp, dtype=float)
            probs = smp_arr[-1]
            states = np.argmax(smp_arr, axis=1)

        current = int(np.argmax(probs))
        trans = np.squeeze(np.asarray(result.regime_transition, dtype=float), axis=-1)
        if trans.ndim != 2:
            trans = trans.reshape(n_states, n_states)
        next_probs = probs @ trans

        param_map = dict(zip(result.model.param_names, result.params))
        mus = np.array([float(param_map.get(f"const[{i}]", 0.0)) for i in range(n_states)])
        phis = np.array([float(param_map.get(f"ar.L1[{i}]", 0.0)) for i in range(n_states)])
        sigmas = np.full(n_states, float(param_map.get("sigma2", 0.01)))

        return {
            "current": current,
            "probs": probs,
            "next_probs": next_probs,
            "trans": trans,
            "mus": mus,
            "phis": phis,
            "sigmas": sigmas,
            "states": states,
        }
    except Exception:
        return None


def _state_semantics(mus: np.ndarray, sigmas: np.ndarray, n_states: int) -> list[str]:
    order = np.argsort(mus)
    names = ["bear", "range", "bull"] if n_states == 3 else ["bear", "range", "bull", "crisis"]
    labels = [""] * n_states
    crisis_idx = int(np.argmax(sigmas))
    if n_states >= 4:
        labels[crisis_idx] = "crisis"
        remaining = [i for i in range(n_states) if i != crisis_idx]
        remaining.sort(key=lambda i: mus[i])
        cycle = ["bear", "range", "bull"]
        for j, idx in enumerate(remaining):
            labels[idx] = cycle[min(j, len(cycle) - 1)]
        return labels
    for j, idx in enumerate(order):
        labels[idx] = names[min(j, len(names) - 1)]
    return labels


def fit_msar_regime(df: pd.DataFrame, *, n_states: int = 3) -> MsarRegimeResult:
    close = df["close"].astype(float)
    ret = np.log(close / close.shift(1)).dropna().to_numpy()

    backend = "builtin_em"
    fit = _fit_statsmodels_msar(ret, n_states=n_states)
    if fit is None:
        fit = _fit_msar_em(ret, n_states=n_states)
    else:
        backend = "statsmodels"

    state_labels = _state_semantics(fit["mus"], fit["sigmas"], n_states)
    current = fit["current"]
    label = state_labels[current]
    conf = float(fit["probs"][current])
    next_idx = int(np.argmax(fit["next_probs"]))
    next_label = state_labels[next_idx]

    trend_map = {"bull": "uptrend", "bear": "downtrend", "crisis": "downtrend"}
    vol_map = {"crisis": "high_vol", "bear": "mid_vol", "bull": "low_vol"}
    raw_trend = trend_map.get(label, "range")
    vol_bucket = vol_map.get(label, "mid_vol")

    drivers = [
        f"状态 {current} ({label}) AR(1) φ={fit['phis'][current]:.3f}",
        f"均值 μ={fit['mus'][current]:.5f} σ={fit['sigmas'][current]:.5f}",
        f"下一步预测 → {next_label}",
        f"后端: {backend}",
    ]
    state_probs = {state_labels[i]: round(float(fit["probs"][i]), 4) for i in range(n_states)}

    return MsarRegimeResult(
        label=label,
        raw_trend=raw_trend,
        vol_bucket=vol_bucket,
        confidence=conf,
        next_label=next_label,
        state_probs=state_probs,
        drivers=drivers,
        metadata={
            "mus": [round(float(x), 6) for x in fit["mus"]],
            "phis": [round(float(x), 4) for x in fit["phis"]],
            "state_labels": state_labels,
        },
        backend=backend,
    )

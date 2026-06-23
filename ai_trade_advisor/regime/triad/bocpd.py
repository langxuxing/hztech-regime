from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BocpdResult:
    changepoint_prob: float
    run_length: int
    in_transition: bool
    label: str

    def to_dict(self) -> dict:
        return {
            "changepoint_prob": round(self.changepoint_prob, 4),
            "run_length": self.run_length,
            "in_transition": self.in_transition,
            "label": self.label,
        }


def _student_t_log_pred(x: float, mu: float, kappa: float, alpha: float, beta: float) -> float:
    nu = 2.0 * alpha
    scale = beta * (kappa + 1.0) / (alpha * kappa)
    scale = max(scale, 1e-12)
    z = (x - mu) ** 2 / scale
    return -0.5 * (nu + 1.0) * np.log1p(z / nu) - 0.5 * np.log(scale * nu * np.pi)


def _update_nig(
    mu: float, kappa: float, alpha: float, beta: float, x: float
) -> tuple[float, float, float, float]:
    kappa_n = kappa + 1.0
    mu_n = (kappa * mu + x) / kappa_n
    alpha_n = alpha + 0.5
    beta_n = beta + 0.5 * kappa * (x - mu) ** 2 / kappa_n
    return mu_n, kappa_n, alpha_n, beta_n


def detect_changepoint(
    series: np.ndarray,
    *,
    hazard_lambda: float = 80.0,
    transition_threshold: float = 0.28,
) -> BocpdResult:
    """简化 Gaussian BOCPD（Adams & MacKay 2007），用于在线变点概率。"""
    x = np.asarray(series, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 8:
        return BocpdResult(0.0, len(x), False, "数据不足")

    hazard = 1.0 / max(hazard_lambda, 1.0)
    mu0, kappa0, alpha0, beta0 = float(np.mean(x)), 1.0, 1.0, float(np.var(x) + 1e-6)

    max_run = min(len(x), 256)
    log_r = np.full(max_run + 1, -np.inf)
    log_r[0] = 0.0
    mus = np.full(max_run + 1, mu0)
    kappas = np.full(max_run + 1, kappa0)
    alphas = np.full(max_run + 1, alpha0)
    betas = np.full(max_run + 1, beta0)

    for obs in x:
        pred_probs = np.empty(max_run + 1)
        for r in range(max_run + 1):
            if not np.isfinite(log_r[r]):
                pred_probs[r] = -np.inf
            else:
                pred_probs[r] = log_r[r] + _student_t_log_pred(obs, mus[r], kappas[r], alphas[r], betas[r])

        growth = np.empty(max_run + 1)
        growth[1:] = pred_probs[:-1] + np.log1p(-hazard)
        growth[0] = np.log(hazard) + pred_probs[0]
        if np.isfinite(pred_probs).any():
            growth[0] = np.logaddexp(growth[0], np.log(hazard) + np.max(pred_probs))

        m = np.max(growth)
        if not np.isfinite(m):
            log_r[:] = 0.0
            log_r[0] = 0.0
            continue
        log_r = growth - m

        new_mus = np.empty(max_run + 1)
        new_kappas = np.empty(max_run + 1)
        new_alphas = np.empty(max_run + 1)
        new_betas = np.empty(max_run + 1)
        new_mus[0], new_kappas[0], new_alphas[0], new_betas[0] = mu0, kappa0, alpha0, beta0
        for r in range(max_run):
            new_mus[r + 1], new_kappas[r + 1], new_alphas[r + 1], new_betas[r + 1] = _update_nig(
                mus[r], kappas[r], alphas[r], betas[r], obs
            )
        mus, kappas, alphas, betas = new_mus, new_kappas, new_alphas, new_betas

    probs = np.exp(log_r - np.max(log_r))
    probs /= probs.sum() + 1e-12
    cp_prob = float(probs[0])
    run_length = int(np.argmax(probs[1:]) + 1) if len(probs) > 1 else 0
    in_transition = cp_prob >= transition_threshold

    if in_transition:
        label = f"变点概率 {cp_prob:.0%}，Regime 切换窗口"
    else:
        label = f"结构稳定 run={run_length} bars"

    return BocpdResult(cp_prob, run_length, in_transition, label)

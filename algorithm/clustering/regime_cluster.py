from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture

from algorithm.common.features import build_cluster_features, normalize_features, recent_return_window


@dataclass
class ClusteringRegimeResult:
    sem_label: str
    raw_trend: str
    vol_bucket: str
    cluster_id: int
    kmeans_cluster: int
    confidence: float
    state_probs: dict[str, float]
    drivers: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def _label_cluster(centroid: np.ndarray) -> tuple[str, str, str]:
    ret_mu = float(centroid[0])
    vol_mu = float(centroid[1]) if len(centroid) > 1 else 0.0
    if vol_mu > 0.8:
        return "crisis", "downtrend", "high_vol"
    if ret_mu > 0.25:
        return "bull", "uptrend", "low_vol"
    if ret_mu < -0.25:
        return "bear", "downtrend", "mid_vol"
    return "range", "range", "mid_vol"


def _dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    n, m = len(a), len(b)
    dp = np.full((n + 1, m + 1), np.inf)
    dp[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = abs(a[i - 1] - b[j - 1])
            dp[i, j] = cost + min(dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1])
    return float(dp[n, m] / (n + m))


def fit_clustering_regime(
    df: pd.DataFrame, *, n_clusters: int = 4, dtw_window: int = 24
) -> ClusteringRegimeResult:
    """K-Means + GMM 聚类，DTW 形态匹配辅助 (scikit-learn)。"""
    feat = build_cluster_features(df)
    x = normalize_features(feat.to_numpy(dtype=float))

    kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
    km_labels = kmeans.fit_predict(x)

    gmm = GaussianMixture(n_components=n_clusters, n_init=3, random_state=42)
    gmm.fit(x)
    gmm_probs = gmm.predict_proba(x)[-1]
    gmm_cluster = int(np.argmax(gmm_probs))
    conf = float(gmm_probs[gmm_cluster])
    km_cluster = int(km_labels[-1])
    cluster_id = gmm_cluster

    sem_label, raw_trend, vol_bucket = _label_cluster(gmm.means_[gmm_cluster])
    state_probs = {f"cluster_{i}": round(float(gmm_probs[i]), 4) for i in range(n_clusters)}

    dtw_notes: list[str] = []
    try:
        recent = recent_return_window(df, window=dtw_window)
        cluster_windows: dict[int, list[float]] = {i: [] for i in range(n_clusters)}
        assign = gmm.predict(x)
        ret_series = feat["ret"].to_numpy()
        for i in range(max(0, len(ret_series) - 120), len(ret_series)):
            cid = int(assign[i])
            start = max(0, i - dtw_window + 1)
            w = ret_series[start : i + 1]
            if len(w) == dtw_window:
                w_norm = (w - w.mean()) / (w.std() + 1e-8)
                cluster_windows[cid].append(_dtw_distance(recent, w_norm))

        dtw_scores = {c: (min(v) if v else np.inf) for c, v in cluster_windows.items()}
        if dtw_scores and min(dtw_scores.values()) < np.inf:
            dtw_best = min(dtw_scores, key=dtw_scores.get)  # type: ignore[arg-type]
            dtw_notes.append(f"DTW 形态匹配 → cluster_{dtw_best}")
            if dtw_best != cluster_id and dtw_scores[dtw_best] < dtw_scores.get(cluster_id, np.inf) * 0.85:
                cluster_id = dtw_best
                conf = conf * 0.92
                sem_label, raw_trend, vol_bucket = _label_cluster(gmm.means_[cluster_id])
    except Exception as exc:
        dtw_notes.append(f"DTW 跳过: {exc}")

    drivers = [
        f"GMM 簇 {cluster_id} (后验 {conf:.0%})",
        f"KMeans 当前簇 {km_cluster}",
        "特征: 收益/波动/成交量/振幅/动量",
    ]
    drivers.extend(dtw_notes)

    return ClusteringRegimeResult(
        sem_label=sem_label,
        raw_trend=raw_trend,
        vol_bucket=vol_bucket,
        cluster_id=cluster_id,
        kmeans_cluster=km_cluster,
        confidence=conf,
        state_probs=state_probs,
        drivers=drivers,
        metadata={
            "gmm_cluster": cluster_id,
            "kmeans_cluster": km_cluster,
            "n_clusters": n_clusters,
            "dtw_window": dtw_window,
        },
    )

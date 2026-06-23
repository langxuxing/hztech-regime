from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from algorithm import (
    fit_clustering_regime,
    fit_heuristic_regime,
    fit_hmm_regime,
    fit_hybrid_regime,
    fit_msar_regime,
)
from algorithm.common.features import build_cluster_features, build_regime_features, normalize_features


def _synthetic_df(n: int = 240, *, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    price = 60000.0
    rows = []
    for i in range(n):
        if i < 80:
            drift, vol = 0.0015, 0.004
        elif i < 160:
            drift, vol = -0.002, 0.009
        else:
            drift, vol = 0.0002, 0.003
        ret = drift + vol * rng.standard_normal()
        price *= 1.0 + ret
        rows.append(
            {
                "close": price,
                "open": price,
                "high": price * 1.002,
                "low": price * 0.998,
                "volume": 100.0 + rng.uniform(0, 50),
            }
        )
    return pd.DataFrame(rows)


def test_algorithm_package_imports():
  import algorithm

  assert hasattr(algorithm, "fit_hmm_regime")
  assert hasattr(algorithm, "fit_clustering_regime")
  assert hasattr(algorithm, "fit_msar_regime")


def test_common_features():
    df = _synthetic_df(120)
    x = build_regime_features(df)
    assert x.ndim == 2 and x.shape[0] >= 30
    feat = build_cluster_features(df)
    assert len(feat) >= 30
    normed = normalize_features(feat.to_numpy())
    assert normed.shape == feat.shape


def test_hmm_algorithm():
    hmm, trans, labels = fit_hmm_regime(_synthetic_df(), n_states=4)
    assert hmm.n_states == 4
    assert len(labels) == 4
    assert trans.shape == (4, 4)
    assert hmm.current_label in labels


def test_clustering_algorithm():
    r = fit_clustering_regime(_synthetic_df())
    assert r.raw_trend in ("uptrend", "downtrend", "range")
    assert 0 < r.confidence <= 1


def test_msar_algorithm():
    r = fit_msar_regime(_synthetic_df())
    assert r.label in ("bull", "bear", "range", "crisis")
    assert r.backend in ("statsmodels", "builtin_em")
    assert r.next_label in ("bull", "bear", "range", "crisis")


def test_hybrid_algorithm():
    r = fit_hybrid_regime(_synthetic_df())
    assert r.pred_label in ("bull", "bear", "range", "crisis")
    assert r.state_probs is not None


def test_heuristic_algorithm():
    r = fit_heuristic_regime(_synthetic_df())
    assert r.regime_id
    assert "adx" in r.metadata


@pytest.mark.parametrize("n_bars", [20, 29])
def test_insufficient_bars_raises(n_bars: int):
    df = _synthetic_df(n_bars)
    with pytest.raises(ValueError):
        build_regime_features(df)

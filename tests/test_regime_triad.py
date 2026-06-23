from __future__ import annotations

import numpy as np
import pandas as pd

from ai_trade_advisor.regime.triad.bocpd import detect_changepoint
from ai_trade_advisor.regime.triad.fusion import fuse_regime_triad, triad_from_dataframe
from ai_trade_advisor.regime.triad.hmm_regime import build_regime_features, fit_hmm_regime


def _synthetic_df(n: int = 240, *, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    price = 60000.0
    rows = []
    for i in range(n):
        if i < 80:
            drift = 0.0015
            vol = 0.004
        elif i < 160:
            drift = -0.002
            vol = 0.009
        else:
            drift = 0.0002
            vol = 0.003
        ret = drift + vol * rng.standard_normal()
        price *= 1.0 + ret
        rows.append({"close": price, "open": price, "high": price * 1.001, "low": price * 0.999, "volume": 100.0})
    return pd.DataFrame(rows)


def test_bocpd_detects_regime_shift():
    df = _synthetic_df()
    ret = np.log(df["close"] / df["close"].shift(1)).dropna().to_numpy()
    early = detect_changepoint(ret[:90], hazard_lambda=60.0)
    late = detect_changepoint(ret[130:], hazard_lambda=60.0)
    assert early.run_length >= 1
    assert late.changepoint_prob >= 0.0


def test_hmm_features_shape():
    df = _synthetic_df()
    x = build_regime_features(df)
    assert x.ndim == 2
    assert x.shape[0] >= 30


def test_hmm_regime_labels():
    df = _synthetic_df()
    hmm, trans, labels = fit_hmm_regime(df, n_states=4)
    assert hmm.n_states == 4
    assert len(labels) == 4
    assert trans.shape == (4, 4)
    assert hmm.current_label in labels


def test_triad_fusion_with_rule():
    df = _synthetic_df()
    rule = {
        "regime_id": "mid_vol_range",
        "raw_trend": "range",
        "vol_bucket": "mid_vol",
        "confidence": 0.7,
        "dashboard_regime": "range",
    }
    fused = fuse_regime_triad(df, rule)
    assert fused.hmm.current_label
    assert fused.transition.next_label
    assert fused.fusion_confidence > 0
    assert "三型融合" in fused.summary or "规则=" in fused.summary


def test_triad_from_dataframe():
    df = _synthetic_df()
    triad = triad_from_dataframe(df)
    d = triad.to_dict()
    assert "bocpd" in d
    assert "hmm" in d
    assert "transition" in d

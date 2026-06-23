from __future__ import annotations

import numpy as np
import pandas as pd

from ai_trade_advisor.regime.models.ensemble import run_all_regime_models
from ai_trade_advisor.regime.models.heuristic_advanced import run_heuristic_advanced_model
from ai_trade_advisor.regime.models.clustering import run_clustering_model
from ai_trade_advisor.regime.models.msar import run_msar_model
from ai_trade_advisor.regime.models.hybrid import run_hybrid_model
from ai_trade_advisor.regime.models.crypto_lstm import run_crypto_lstm_model
from ai_trade_advisor.regime.models.jayd_regime import run_jayd_regime_model
from ai_trade_advisor.regime.engines.jayd_analysis import analyze_jayd_regime
from ai_trade_advisor.regime.engines.vendor_paths import AKASH_VENDOR, JAYD_VENDOR


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


def _rule() -> dict:
    return {
        "regime_id": "mid_vol_range",
        "regime_label": "中波震荡 · 等待突破",
        "raw_trend": "range",
        "vol_bucket": "mid_vol",
        "confidence": 0.7,
        "dashboard_regime": "range",
    }


def test_run_all_regime_models():
    df = _synthetic_df()
    out = run_all_regime_models(df, _rule())
    models = out["models"]
    assert "heuristic" in models
    assert "hmm" in models
    assert "clustering" in models
    assert "msar" in models
    assert "heuristic_advanced" in models
    assert "hybrid" in models
    assert "crypto_lstm" in models
    assert "jayd_regime" in models
    assert out["comparison"]["model_count"] == 8


def test_clustering_model():
    df = _synthetic_df()
    r = run_clustering_model(df)
    assert r.model_id == "clustering"
    assert r.confidence > 0
    assert r.raw_trend in ("uptrend", "downtrend", "range")


def test_msar_model():
    df = _synthetic_df()
    r = run_msar_model(df)
    assert r.model_id == "msar"
    assert r.next_regime_label is not None


def test_heuristic_advanced_model():
    df = _synthetic_df()
    r = run_heuristic_advanced_model(df)
    assert r.model_id == "heuristic_advanced"
    assert "adx" in r.metadata


def test_hybrid_model():
    df = _synthetic_df()
    r = run_hybrid_model(df)
    assert r.model_id == "hybrid"
    assert r.state_probs is not None


def test_jayd_regime_model():
    assert JAYD_VENDOR.exists(), "jayd vendor repo should be cloned under vendor/"
    df = _synthetic_df(n=200)
    r = run_jayd_regime_model(df)
    assert r.model_id == "jayd_regime"
    assert r.error is None
    assert r.raw_trend in ("uptrend", "downtrend", "range")
    assert r.confidence > 0


def test_jayd_analysis_engine():
    df = _synthetic_df(n=200)
    out = analyze_jayd_regime(df)
    assert out.error is None
    assert out.dt_regime in ("Trending Up", "Trending Down", "Sideways")
    assert out.hmm_state in ("Low Volatility", "High Volatility")


def test_crypto_lstm_model_registered():
    assert AKASH_VENDOR.exists(), "akash vendor repo should be cloned under vendor/"
    df = _synthetic_df(n=300)
    r = run_crypto_lstm_model(df)
    assert r.model_id == "crypto_lstm"
    if r.error:
        err = r.error.lower()
        assert any(
            kw in err
            for kw in ("tensorflow", "need at least", "missing", "fetch", "network", "ohlcv")
        )
    else:
        assert r.confidence > 0
        assert r.regime_label.startswith(("LSTM ·", "HMM ·"))

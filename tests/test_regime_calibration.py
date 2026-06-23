from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_trade_advisor.regime.feedback.calibrator import _calibrate_ensemble_weights, _normalize_weights
from ai_trade_advisor.regime.feedback.replay import replay_param_grid
from ai_trade_advisor.regime.feedback.store import FeedbackStore


def _synthetic_df(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(2)
    price = 60000.0
    rows = []
    for i in range(n):
        drift = 0.002 if i > 100 else -0.001
        price *= 1.0 + drift + 0.003 * rng.standard_normal()
        rows.append(
            {
                "close": price,
                "open": price,
                "high": price * 1.002,
                "low": price * 0.998,
                "volume": 100.0,
            }
        )
    return pd.DataFrame(rows)


def test_normalize_weights():
    w = _normalize_weights({"hmm": 0.9, "clustering": 0.3})
    assert abs(sum(w.values()) - 1.0) < 0.01
    assert w["hmm"] > w["clustering"]


def test_calibrate_ensemble_weights(tmp_path):
    store = FeedbackStore(tmp_path / "r.db")
    store.upsert_rollup(
        [
            {
                "symbol": "BTC/USDT:USDT",
                "segment_primary": "global",
                "model_id": "hmm",
                "window_days": 30,
                "sample_count": 10,
                "instant_avg": 0.8,
                "forward_avg": 0.85,
                "combined_score": 0.83,
                "low_confidence": False,
            },
            {
                "symbol": "BTC/USDT:USDT",
                "segment_primary": "global",
                "model_id": "msar",
                "window_days": 30,
                "sample_count": 10,
                "instant_avg": 0.5,
                "forward_avg": 0.55,
                "combined_score": 0.53,
                "low_confidence": False,
            },
        ]
    )
    params, score, meta = _calibrate_ensemble_weights(store, 30)
    assert params["weights"]["hmm"] > params["weights"]["msar"]
    assert score > 0


def test_replay_param_grid():
    df = _synthetic_df(200)
    judgments = [
        {
            "bar_close": float(df.iloc[120]["close"]),
            "recorded_at": "2026-01-01T00:00:00+00:00",
            "realized_regime": {
                "realized_trend": "uptrend",
                "realized_dashboard": "trend_up",
            },
        },
        {
            "bar_close": float(df.iloc[160]["close"]),
            "recorded_at": "2026-01-02T00:00:00+00:00",
            "realized_regime": {
                "realized_trend": "uptrend",
                "realized_dashboard": "trend_up",
            },
        },
    ]
    grid = [{"n_states": 3}, {"n_states": 4}]
    best, score = replay_param_grid(df, judgments, "hmm", grid)
    assert "n_states" in best
    assert score >= 0

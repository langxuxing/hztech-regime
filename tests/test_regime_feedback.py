from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_trade_advisor.regime.feedback.realized import compute_realized_regime
from ai_trade_advisor.regime.feedback.scoring import score_judgment_instant, score_model_against_truth
from ai_trade_advisor.regime.feedback.market_context import build_market_context
from ai_trade_advisor.regime.feedback.store import FeedbackStore
from ai_trade_advisor.regime.feedback.rollup import refresh_rollup
from ai_trade_advisor.regime.feedback.recommender import recommend_model
from ai_trade_advisor.regime.feedback.params_store import ModelParamsCache
from ai_trade_advisor.regime.judgment_store import HumanJudgmentStore
from ai_trade_advisor.regime.feedback.service import record_human_judgment_with_scoring


def _synthetic_df(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    price = 60000.0
    rows = []
    for _ in range(n):
        price *= 1.0 + 0.001 + 0.004 * rng.standard_normal()
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


@pytest.fixture
def feedback_db(tmp_path):
    db = tmp_path / "regime.db"
    j = HumanJudgmentStore(db)
    f = FeedbackStore(db)
    return j, f


def test_score_model_against_truth():
    model = {
        "raw_trend": "uptrend",
        "dashboard_regime": "trend_up",
        "next_regime_label": "bull",
        "confidence": 0.8,
    }
    scored = score_model_against_truth(model, human_regime="trend_up", human_trend="uptrend")
    assert scored["total_score"] >= 0.85


def test_instant_scoring_on_judgment():
    judgment = {
        "id": 1,
        "human_regime": "trend_up",
        "human_trend": "uptrend",
        "model_predictions": {
            "models": {
                "hmm": {
                    "raw_trend": "uptrend",
                    "dashboard_regime": "trend_up",
                    "confidence": 0.7,
                }
            }
        },
    }
    scores = score_judgment_instant(judgment)
    assert len(scores) == 1
    assert scores[0]["model_id"] == "hmm"


def test_market_context_segment():
    ctx = build_market_context(
        {
            "regime_id": "low_vol_uptrend",
            "raw_trend": "uptrend",
            "vol_bucket": "low_vol",
            "dashboard_regime": "trend_up",
        }
    )
    assert ctx["segment_primary"] == "low_vol_uptrend"


def test_realized_regime():
    df = _synthetic_df(80)
    for i in range(40, 80):
        df.loc[i, "close"] = 60000 + i * 50
    realized = compute_realized_regime(df, 30, forward_bars=6)
    assert realized is not None
    assert realized["realized_trend"] in ("uptrend", "range", "downtrend")


def test_record_and_rollup(feedback_db):
    jstore, fstore = feedback_db
    btc = {
        "close": 60000.0,
        "regime_id": "mid_vol_range",
        "raw_trend": "range",
        "vol_bucket": "mid_vol",
        "dashboard_regime": "range",
        "models": {
            "hmm": {
                "raw_trend": "uptrend",
                "dashboard_regime": "trend_up",
                "confidence": 0.6,
            }
        },
    }
    result = record_human_judgment_with_scoring(
        "BTC/USDT:USDT",
        human_regime="trend_up",
        human_trend="uptrend",
        btc_regime=btc,
        judgment_store=jstore,
        feedback_store=fstore,
    )
    assert result["id"] > 0
    assert "hmm" in result["scores"]

    # simulate forward score
    fstore.save_scores(
        [
            {
                "judgment_id": result["id"],
                "model_id": "hmm",
                "score_type": "forward",
                "trend_score": 0.9,
                "regime_score": 0.9,
                "pred_score": None,
                "total_score": 0.9,
                "scored_at": "2026-01-01T00:00:00+00:00",
                "details": {},
            }
        ]
    )
    rows = refresh_rollup(fstore, window_days=30, min_samples=1)
    assert rows

    rec = recommend_model({"segment_primary": "mid_vol_range"}, symbol="BTC/USDT:USDT", store=fstore, min_samples=1)
    assert "best_model_id" in rec


def test_params_cache_defaults(feedback_db):
    _, fstore = feedback_db
    cache = ModelParamsCache(fstore)
    assert cache.get_params("hmm")["n_states"] == 4

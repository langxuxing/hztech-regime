"""Tests for regime matrix serialization."""

from ai_trade_advisor.regime.matrix import build_hmm_probs, build_regime_matrix, enrich_regime_dict


def test_build_regime_matrix_uptrend_high_vol():
    regime = {
        "regime_id": "high_vol_uptrend",
        "raw_trend": "uptrend",
        "vol_bucket": "high_vol",
        "confidence": 0.8,
        "confirmation": {
            "combined": {
                "confirmed_regime_id": "high_vol_uptrend",
                "live_regime_id": "high_vol_uptrend",
            }
        },
    }
    matrix = build_regime_matrix(regime)
    assert matrix["current_cell"] == "high_vol_uptrend"
    assert matrix["confirmed_cell"] == "high_vol_uptrend"


def test_build_hmm_probs_from_triad():
    regime = {
        "regime_id": "high_vol_uptrend",
        "confidence": 0.7,
        "triad": {
            "hmm": {
                "state_probs": [0.1, 0.2, 0.6, 0.1],
                "state_labels": ["bear", "range", "bull", "crisis"],
                "vol_hint": "high_vol",
            }
        },
    }
    probs = build_hmm_probs(regime)
    assert probs["high_vol_uptrend"] == 0.6


def test_enrich_regime_dict_adds_matrix_and_probs():
    out = enrich_regime_dict(
        {
            "regime_id": "low_vol_range",
            "raw_trend": "range",
            "vol_bucket": "low_vol",
        }
    )
    assert "matrix" in out
    assert "hmm_probs" in out

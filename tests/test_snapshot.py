"""快照存储与聚合测试。"""

from __future__ import annotations

import json

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.snapshot.store import SnapshotStore, snapshot_key


def test_snapshot_store_roundtrip(tmp_path):
    store = SnapshotStore(root=tmp_path)
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT")
    key = snapshot_key(cfg)
    payload = {
        **SnapshotStore.new_version(),
        "exchange": cfg.exchange,
        "symbol": cfg.symbol,
        "dashboard": {"symbol": cfg.symbol},
    }
    store.save(key, payload)
    loaded = store.get(key)
    assert loaded is not None
    assert loaded["symbol"] == "BTC/USDT:USDT"
    assert loaded["snapshot_id"] == payload["snapshot_id"]
    assert not store.is_stale(key, max_age_sec=3600)


def test_snapshot_is_stale_when_missing(tmp_path):
    store = SnapshotStore(root=tmp_path)
    assert store.is_stale("missing", max_age_sec=60)


def test_l3_advice_scoring_instant():
    from ai_trade_advisor.regime.feedback.scoring import score_judgment_instant

    judgment = {
        "id": 1,
        "human_regime": "trend_up",
        "human_trend": "uptrend",
        "model_predictions": {
            "board_regime": "range",
            "advice": {
                "bias": "long",
                "confidence": 0.8,
            },
        },
    }
    scores = score_judgment_instant(judgment)
    assert any(s["model_id"] == "trade_advice" for s in scores)
    advice_score = next(s for s in scores if s["model_id"] == "trade_advice")
    assert advice_score["trend_score"] == 1.0
    assert advice_score["regime_score"] < 1.0

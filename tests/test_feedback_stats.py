"""反馈统计 API 与 build_feedback_stats 测试。"""

from __future__ import annotations

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.regime.feedback.stats import RECOMMENDATION_MIN_JUDGMENTS, build_feedback_stats
from ai_trade_advisor.regime.feedback.store import FeedbackStore
from ai_trade_advisor.regime.judgment_store import HumanJudgmentStore
from ai_trade_advisor.regime.feedback.service import record_human_judgment_with_scoring
from ai_trade_advisor.api_auth import register_api_auth
from ai_trade_advisor.api_server import app


def test_feedback_stats_empty(tmp_path):
    jstore = HumanJudgmentStore(db_path=tmp_path / "regime.db")
    fstore = FeedbackStore(db_path=tmp_path / "regime.db")
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT", data_dir=tmp_path)
    stats = build_feedback_stats(
        symbol=cfg.symbol,
        cfg=cfg,
        judgment_store=jstore,
        feedback_store=fstore,
    )
    assert stats["judgment_count"] == 0
    assert stats["recommendation_ready"] is False
    assert stats["min_judgments_for_recommendation"] == RECOMMENDATION_MIN_JUDGMENTS


def test_feedback_stats_after_record(tmp_path):
    db = tmp_path / "regime.db"
    jstore = HumanJudgmentStore(db)
    fstore = FeedbackStore(db)
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT")
    btc = {
        "regime_id": "mid_vol_uptrend",
        "raw_trend": "uptrend",
        "dashboard_regime": "trend_up",
        "models": {
            "heuristic": {
                "model_id": "heuristic",
                "regime_id": "mid_vol_uptrend",
                "raw_trend": "uptrend",
                "dashboard_regime": "trend_up",
            }
        },
    }
    record_human_judgment_with_scoring(
        cfg.symbol,
        human_regime="trend_up",
        human_trend="uptrend",
        btc_regime=btc,
        judgment_store=jstore,
        feedback_store=fstore,
    )
    stats = build_feedback_stats(
        symbol=cfg.symbol,
        cfg=cfg,
        judgment_store=jstore,
        feedback_store=fstore,
        min_judgments=1,
    )
    assert stats["judgment_count"] == 1
    assert stats["latest_judgment_at"] is not None


def test_feedback_stats_api(monkeypatch):
    register_api_auth(app, "")
    monkeypatch.setattr(
        "ai_trade_advisor.api_server.build_feedback_stats",
        lambda **kwargs: {
            "symbol": "BTC/USDT:USDT",
            "judgment_count": 5,
            "forward_scored_count": 2,
            "min_judgments_for_recommendation": 30,
            "recommendation_ready": False,
            "message": "test",
        },
    )
    client = app.test_client()
    resp = client.get("/api/regime/feedback-stats?symbol=BTC/USDT:USDT")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["judgment_count"] == 5
    assert body["recommendation_ready"] is False


def test_judgment_store_counts(tmp_path):
    jstore = HumanJudgmentStore(db_path=tmp_path / "counts.db")
    assert jstore.count() == 0
    jstore.record("BTC/USDT:USDT", human_regime="range", human_trend="range")
    assert jstore.count(symbol="BTC/USDT:USDT") == 1
    assert jstore.count_forward_scored(symbol="BTC/USDT:USDT") == 0

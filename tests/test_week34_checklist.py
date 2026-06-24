"""第 3–4 周验收清单与推荐门控测试。"""

from __future__ import annotations

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.ops.week34_checklist import run_week34_checklist
from ai_trade_advisor.regime.feedback.stats import (
    RECOMMENDATION_MIN_JUDGMENTS,
    build_feedback_stats,
    should_apply_recommendation_fusion,
)
from ai_trade_advisor.regime.feedback.store import FeedbackStore
from ai_trade_advisor.regime.judgment_store import HumanJudgmentStore
from ai_trade_advisor.regime.feedback.service import record_human_judgment_with_scoring
from ai_trade_advisor.snapshot.store import SnapshotStore, snapshot_key


def test_should_apply_recommendation_requires_ready_stats(tmp_path):
    cfg = AdvisorConfig(
        exchange="binance",
        symbol="BTC/USDT:USDT",
        data_dir=tmp_path,
        regime_use_recommendation=True,
    )
    rec = {"best_model_id": "heuristic", "low_confidence": False}
    stats = {
        "recommendation_ready": False,
        "judgment_count": 5,
    }
    assert should_apply_recommendation_fusion(cfg, rec, stats=stats) is False

    stats["recommendation_ready"] = True
    assert should_apply_recommendation_fusion(cfg, rec, stats=stats) is True


def test_should_apply_recommendation_respects_env_off(tmp_path):
    cfg = AdvisorConfig(
        exchange="binance",
        symbol="BTC/USDT:USDT",
        data_dir=tmp_path,
        regime_use_recommendation=False,
    )
    rec = {"best_model_id": "heuristic", "low_confidence": False}
    stats = {"recommendation_ready": True}
    assert should_apply_recommendation_fusion(cfg, rec, stats=stats) is False


def test_week34_checklist_structure(tmp_path, monkeypatch):
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT", data_dir=tmp_path)
    store = SnapshotStore(root=tmp_path / "snap")
    key = snapshot_key(cfg)
    store.save(
        key,
        {
            "trend_judgment": {
                "trend": "uptrend",
                "stability": "confirmed",
                "live_regime_id": "a",
                "confirmed_regime_id": "a",
            }
        },
    )

    class _FreshStore(SnapshotStore):
        def is_stale(self, key, max_age_sec):
            return False

    monkeypatch.setattr(
        "ai_trade_advisor.ops.week34_checklist.SnapshotStore",
        lambda: _FreshStore(root=tmp_path / "snap"),
    )
    monkeypatch.setattr(
        "ai_trade_advisor.ops.week34_checklist.load_local_btc_1m_csvs",
        lambda: None,
    )
    monkeypatch.setattr(
        "ai_trade_advisor.ops.week34_checklist.check_readiness",
        lambda c: type("R", (), {"tier": "demo", "to_dict": lambda self: {"tier": "demo"}})(),
    )

    report = run_week34_checklist(cfg)
    assert isinstance(report.week3_passed, bool)
    assert len(report.checks) >= 8
    weeks = {c.week for c in report.checks}
    assert weeks == {3, 4}


def test_feedback_stats_integration_for_week4(tmp_path):
    db = tmp_path / "regime.db"
    jstore = HumanJudgmentStore(db)
    fstore = FeedbackStore(db)
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT", data_dir=tmp_path)
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
    assert stats["min_judgments_for_recommendation"] == 1

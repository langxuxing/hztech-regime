"""trend_health 模块与 CLI 测试。"""

from __future__ import annotations

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.regime.trend_health import run_trend_health_check
from ai_trade_advisor.snapshot.store import SnapshotStore, snapshot_key


def test_health_check_critical_when_no_snapshot(tmp_path):
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT", data_dir=tmp_path)
    store = SnapshotStore(root=tmp_path / "empty")
    report = run_trend_health_check(cfg, store=store)
    assert report["status"] == "critical"
    assert any(f["title"] == "无雷达快照" for f in report["findings"])


def test_health_check_degraded_when_snapshot_stale(tmp_path):
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT", data_dir=tmp_path)
    store = SnapshotStore(root=tmp_path / "snap")
    key = snapshot_key(cfg)
    store.save(
        key,
        {
            "trend_judgment": {
                "trend": "range",
                "stability": "confirmed",
                "live_regime_id": "a",
                "confirmed_regime_id": "a",
            }
        },
    )
    report = run_trend_health_check(cfg, store=store)
    assert report["status"] == "degraded"
    assert any(f["title"] == "快照过期" for f in report["findings"])


def test_health_check_history_failure_is_degraded(tmp_path, monkeypatch):
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT", data_dir=tmp_path)
    store = SnapshotStore(root=tmp_path / "snap2")
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

    fresh = _FreshStore(root=tmp_path / "snap2")

    class _BrokenHistory:
        def recent(self, **kwargs):
            raise RuntimeError("db broken")

    report = run_trend_health_check(cfg, store=fresh, regime_store=_BrokenHistory())
    assert report["status"] == "degraded"
    assert any(f["title"] == "Regime 历史查询失败" for f in report["findings"])

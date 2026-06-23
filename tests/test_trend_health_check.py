"""trend_health_check 脚本测试。"""

import importlib.util
from pathlib import Path

import pytest

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.snapshot.store import SnapshotStore, snapshot_key

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "trend_health_check",
    ROOT / "scripts" / "trend_health_check.py",
)
health = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(health)


def test_health_check_critical_when_no_snapshot(monkeypatch):
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT")

    class _Store:
        def get(self, key):
            return None

        def is_stale(self, key, max_age_sec):
            return True

    monkeypatch.setattr(health, "SnapshotStore", lambda: _Store())
    monkeypatch.setattr(health, "check_readiness", lambda *a, **k: type("R", (), {"tier": "demo"})())
    monkeypatch.setattr(health.RegimeHistoryStore, "recent", lambda self, **k: [])

    report = health.run_health_check(cfg)
    assert report["status"] == "critical"
    assert any(f["title"] == "无雷达快照" for f in report["findings"])


def test_health_check_degraded_when_snapshot_stale(monkeypatch, tmp_path):
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT")
    store = SnapshotStore(root=tmp_path)
    key = snapshot_key(cfg)
    store.save(key, {"trend_judgment": {"trend": "range", "stability": "confirmed"}})

    monkeypatch.setattr(health, "SnapshotStore", lambda: store)
    monkeypatch.setattr(health, "check_readiness", lambda *a, **k: type("R", (), {"tier": "demo"})())
    monkeypatch.setattr(health.RegimeHistoryStore, "recent", lambda self, **k: [])

    report = health.run_health_check(cfg)
    assert report["status"] == "degraded"
    assert any(f["title"] == "快照过期" for f in report["findings"])


def test_health_check_history_failure_is_degraded(monkeypatch, tmp_path):
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT")
    store = SnapshotStore(root=tmp_path)
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

    class _StaleStore(SnapshotStore):
        def is_stale(self, key, max_age_sec):
            return False

    monkeypatch.setattr(health, "SnapshotStore", lambda: _StaleStore(root=tmp_path))
    monkeypatch.setattr(health, "check_readiness", lambda *a, **k: type("R", (), {"tier": "demo"})())

    def _boom(self, **kwargs):
        raise RuntimeError("db broken")

    monkeypatch.setattr(health.RegimeHistoryStore, "recent", _boom)

    report = health.run_health_check(cfg)
    assert report["status"] == "degraded"
    assert any(f["title"] == "Regime 历史查询失败" for f in report["findings"])

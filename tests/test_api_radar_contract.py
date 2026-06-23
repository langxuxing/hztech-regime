"""Flask /api/radar 与 /api/trend-health 契约测试。"""

from __future__ import annotations

import pytest

from ai_trade_advisor.api_auth import register_api_auth
from ai_trade_advisor.api_server import app
from ai_trade_advisor.regime.trend_judgment import (
    TREND_JUDGMENT_REQUIRED_KEYS,
    validate_trend_judgment,
)


def _sample_bundle() -> dict:
    tj = {
        "trend": "uptrend",
        "trend_label": "上涨",
        "tech_trend": "uptrend",
        "confidence": 0.72,
        "regime_id": "mid_vol_uptrend",
        "regime_label": "中波上行 · 趋势延续",
        "stability": "confirmed",
        "business_stance": "顺势做多 · 中波趋势延续",
        "drivers": ["测试"],
        "data_tier": "demo",
        "needs_human_judgment": False,
        "hmm_disagrees": False,
        "consensus_misaligned": False,
        "consensus_capped": False,
    }
    assert validate_trend_judgment(tj) == []
    return {
        "snapshot_id": "snap-test",
        "version": 1,
        "computed_at": "2024-01-01T00:00:00Z",
        "exchange": "binance",
        "symbol": "BTC/USDT:USDT",
        "as_of": "2024-01-01T00:00:00Z",
        "dashboard": {"symbol": "BTC/USDT:USDT", "btc_regime": {"raw_trend": "uptrend"}},
        "trend_judgment": tj,
        "readiness_tier": "demo",
        "errors": [],
    }


@pytest.fixture
def client(monkeypatch):
    register_api_auth(app, "")
    bundle = _sample_bundle()
    monkeypatch.setattr(
        "ai_trade_advisor.api_server._load_bundle",
        lambda cfg: (bundle, True),
    )
    monkeypatch.setattr(
        "ai_trade_advisor.api_server._snapshot_store.get",
        lambda key: bundle,
    )
    monkeypatch.setattr(
        "ai_trade_advisor.api_server.run_trend_health_check",
        lambda *a, **k: {
            "status": "ok",
            "readiness_tier": "demo",
            "trend_judgment": bundle["trend_judgment"],
            "findings": [],
        },
    )
    return app.test_client()


def test_radar_returns_trend_judgment_contract(client):
    resp = client.get("/api/radar")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["trend_judgment"] is not None
    assert validate_trend_judgment(body["trend_judgment"]) == []
    assert body["readiness_tier"] == "demo"
    assert body["from_cache"] is True


def test_trend_health_endpoint(client):
    resp = client.get("/api/trend-health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["trend_judgment"]["trend"] == "uptrend"


def test_health_includes_trend_summary(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["trend"] == "uptrend"
    assert body["trend_stability"] == "confirmed"


def test_validate_trend_judgment_rejects_invalid():
    errors = validate_trend_judgment({"trend": "sideways", "confidence": 2})
    assert errors
    assert any("trend" in e for e in errors)


def test_required_keys_complete():
    sample = _sample_bundle()["trend_judgment"]
    assert TREND_JUDGMENT_REQUIRED_KEYS <= set(sample.keys())

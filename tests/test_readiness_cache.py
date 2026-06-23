"""readiness 缓存测试。"""

from __future__ import annotations

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.readiness import get_cached_readiness_tier, reset_readiness_cache


def test_readiness_cache_avoids_repeat_calls(monkeypatch):
    reset_readiness_cache()
    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT", readiness_cache_ttl_sec=300)
    calls = {"n": 0}

    def _fake_check(c):
        calls["n"] += 1
        from ai_trade_advisor.readiness import ReadinessReport

        return ReadinessReport(tier="demo")

    monkeypatch.setattr("ai_trade_advisor.readiness.check_readiness", _fake_check)
    assert get_cached_readiness_tier(cfg) == "demo"
    assert get_cached_readiness_tier(cfg) == "demo"
    assert calls["n"] == 1

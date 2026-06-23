from __future__ import annotations

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.readiness import check_readiness


def test_readiness_report_shape() -> None:
    report = check_readiness(AdvisorConfig(symbol="BTC/USDT:USDT"))
    data = report.to_dict()
    assert report.tier in ("production", "degraded", "demo")
    assert "local_btc_1m" in data["checks"]
    assert isinstance(data["notes"], list)

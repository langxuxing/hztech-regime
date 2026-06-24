"""trend_soak 汇总逻辑测试。"""

from __future__ import annotations

from ai_trade_advisor.regime.trend_soak import sample_from_health, summarize_soak_samples


def test_summarize_empty():
    s = summarize_soak_samples([])
    assert s["passed"] is False
    assert s["status"] == "critical"


def test_summarize_all_ok():
    samples = [
        {"status": "ok", "trend": "uptrend", "stability": "confirmed"},
        {"status": "ok", "trend": "uptrend", "stability": "confirmed"},
    ]
    s = summarize_soak_samples(samples)
    assert s["passed"] is True
    assert s["ok_rate"] == 1.0


def test_summarize_critical_fails():
    samples = [
        {"status": "ok", "trend": "range", "stability": "provisional"},
        {"status": "critical", "trend": None, "stability": None},
    ]
    s = summarize_soak_samples(samples)
    assert s["passed"] is False
    assert s["max_critical_streak"] == 1


def test_sample_from_health():
    sample = sample_from_health(
        {
            "generated_at": "2024-01-01T00:00:00Z",
            "status": "ok",
            "readiness_tier": "demo",
            "snapshot_age_sec": 10,
            "trend_judgment": {
                "trend": "uptrend",
                "stability": "confirmed",
                "regime_id": "mid_vol_uptrend",
            },
            "findings": [],
            "regime_flips_recent": 1,
        }
    )
    assert sample["trend"] == "uptrend"
    assert sample["findings_count"] == 0

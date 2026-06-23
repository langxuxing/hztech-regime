"""趋势判断契约、HMM 修正与 Regime 全矩阵测试。"""

from __future__ import annotations

import pytest

from ai_trade_advisor.regime.engine import BtcRegimeAnalysis, _compose_regime
from ai_trade_advisor.regime.hmm_modifier import apply_hmm_confidence_modifier
from ai_trade_advisor.regime.trend_judgment import (
    build_trend_judgment,
    business_stance,
)


def _minimal_btc(**overrides) -> dict:
    base = {
        "raw_trend": "uptrend",
        "tech_trend": "uptrend",
        "regime_id": "mid_vol_uptrend",
        "regime_label": "中波上行 · 趋势延续",
        "confidence": 0.75,
        "dashboard_regime": "trend_up",
        "drivers": ["测试驱动"],
        "derivatives_trend": {"votes_bull": 2, "votes_bear": 0},
    }
    base.update(overrides)
    return base


def test_build_trend_judgment_schema():
    tj = build_trend_judgment(
        _minimal_btc(),
        regime_confirmation={
            "dwell_bars": 2,
            "min_dwell_bars": 2,
            "combined": {
                "live_regime_id": "mid_vol_uptrend",
                "confirmed_regime_id": "mid_vol_uptrend",
            },
        },
        data_tier="demo",
    )
    assert tj is not None
    assert tj["trend"] == "uptrend"
    assert tj["stability"] == "confirmed"
    assert tj["business_stance"] == business_stance("uptrend", "mid_vol_uptrend")
    assert tj["data_tier"] == "demo"
    assert "regime_id" in tj
    assert "drivers" in tj


def test_build_trend_judgment_provisional_when_live_differs():
    tj = build_trend_judgment(
        _minimal_btc(regime_id="low_vol_uptrend"),
        regime_confirmation={
            "dwell_bars": 1,
            "min_dwell_bars": 2,
            "combined": {
                "live_regime_id": "low_vol_uptrend",
                "confirmed_regime_id": "mid_vol_uptrend",
            },
        },
    )
    assert tj["stability"] == "provisional"


def test_consensus_misalignment_caps_confidence():
    tj = build_trend_judgment(
        _minimal_btc(confidence=0.82),
        consensus={"direction": "down", "label": "偏空", "score": -0.2, "agreement": 0.7},
    )
    assert tj["confidence"] <= 0.55
    assert tj["consensus_capped"] is True
    assert tj["consensus_alignment"]["aligned"] is False


def test_hmm_disagreement_lowers_confidence():
    analysis = BtcRegimeAnalysis(
        regime_id="mid_vol_uptrend",
        regime_label="中波上行",
        raw_trend="uptrend",
        vol_bucket="mid_vol",
        close=100.0,
        donchian_upper=95,
        donchian_lower=85,
        kama=98,
        kama_upper=99,
        kama_lower=97,
        spot_cvd=1.0,
        spot_cvd_breakout=False,
        cvd_bullish_divergence=False,
        spot_premium_bps=None,
        spot_premium_positive=False,
        macro_hazard=False,
        confidence=0.80,
    )
    models = {
        "hmm": {
            "raw_trend": "downtrend",
            "confidence": 0.72,
            "model_id": "hmm",
        }
    }
    updated, meta = apply_hmm_confidence_modifier(analysis, models)
    assert meta["applied"] is True
    assert meta["reason"] == "trend_disagreement"
    assert updated.confidence <= 0.55
    assert updated.in_regime_transition is True


def test_hmm_agreement_keeps_confidence():
    analysis = BtcRegimeAnalysis(
        regime_id="mid_vol_uptrend",
        regime_label="中波上行",
        raw_trend="uptrend",
        vol_bucket="mid_vol",
        close=100.0,
        donchian_upper=95,
        donchian_lower=85,
        kama=98,
        kama_upper=99,
        kama_lower=97,
        spot_cvd=1.0,
        spot_cvd_breakout=False,
        cvd_bullish_divergence=False,
        spot_premium_bps=None,
        spot_premium_positive=False,
        macro_hazard=False,
        confidence=0.80,
    )
    models = {"hmm": {"raw_trend": "uptrend", "confidence": 0.85}}
    updated, meta = apply_hmm_confidence_modifier(analysis, models)
    assert meta["applied"] is False
    assert updated.confidence == 0.80


@pytest.mark.parametrize(
    "raw_trend,vol_bucket,cvd_breakout,cvd_div,expected",
    [
        ("uptrend", "high_vol", True, False, "high_vol_uptrend"),
        ("uptrend", "high_vol", False, False, "fake_breakout_wash"),
        ("uptrend", "mid_vol", False, False, "mid_vol_uptrend"),
        ("uptrend", "low_vol", False, False, "low_vol_uptrend"),
        ("downtrend", "high_vol", False, False, "high_vol_downtrend"),
        ("downtrend", "low_vol", False, False, "low_vol_downtrend"),
        ("downtrend", "high_vol", False, True, "high_vol_self_heal_range"),
        ("downtrend", "mid_vol", False, True, "high_vol_self_heal_range"),
        ("downtrend", "low_vol", False, True, "low_vol_downtrend"),
        ("range", "low_vol", False, False, "low_vol_range"),
        ("range", "mid_vol", False, False, "mid_vol_range"),
        ("range", "high_vol", False, False, "high_vol_range"),
    ],
)
def test_compose_regime_full_matrix(raw_trend, vol_bucket, cvd_breakout, cvd_div, expected):
    drivers: list[str] = []
    rid = _compose_regime(raw_trend, vol_bucket, cvd_breakout, cvd_div, drivers, {})
    assert rid == expected


def test_business_stance_fake_breakout():
    assert "减仓" in business_stance("uptrend", "fake_breakout_wash")


def test_radar_bundle_includes_trend_judgment(monkeypatch):
    from ai_trade_advisor.config import AdvisorConfig
    from ai_trade_advisor.snapshot import bundle as snap_bundle

    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT")

    fake_dashboard = {
        "symbol": cfg.symbol,
        "btc_regime": _minimal_btc(),
        "regime_confirmation": {
            "dwell_bars": 2,
            "min_dwell_bars": 2,
            "combined": {
                "live_regime_id": "mid_vol_uptrend",
                "confirmed_regime_id": "mid_vol_uptrend",
            },
        },
    }

    def _fake_core(*args, **kwargs):
        return {
            **snap_bundle.SnapshotStore.new_version(),
            "exchange": cfg.exchange,
            "symbol": cfg.symbol,
            "as_of": "2024-01-01T00:00:00Z",
            "dashboard": fake_dashboard,
            "state_machine": {},
            "models": {},
        }

    class _FakeConsensus:
        def to_dict(self):
            return {"direction": "up", "label": "偏多"}

    monkeypatch.setattr(snap_bundle, "compute_dashboard_snapshot", _fake_core)
    monkeypatch.setattr(snap_bundle, "run_event_analysis", lambda *a, **k: (_ for _ in ()).throw(Exception("skip")))
    monkeypatch.setattr(snap_bundle, "fetch_from_config", lambda *a, **k: _FakeConsensus())
    monkeypatch.setattr(snap_bundle, "check_readiness", lambda *a, **k: type("R", (), {"tier": "demo"})())

    class _Store:
        def recent(self, **kwargs):
            return []

    result = snap_bundle.build_radar_bundle(cfg, regime_store=_Store())
    assert result.get("trend_judgment") is not None
    assert result["trend_judgment"]["trend"] == "uptrend"
    assert result["readiness_tier"] == "demo"

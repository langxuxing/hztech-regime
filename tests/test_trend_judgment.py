"""趋势判断契约、HMM 修正与 Regime 全矩阵测试。"""

from __future__ import annotations

import pytest

from ai_trade_advisor.regime.engine import BtcRegimeAnalysis, _compose_regime
from ai_trade_advisor.regime.hmm_modifier import apply_hmm_confidence_modifier
from ai_trade_advisor.regime.trend_judgment import (
    apply_consensus_confidence_cap,
    build_trend_judgment,
    business_stance,
    validate_trend_judgment,
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


def test_build_trend_judgment_none():
    assert build_trend_judgment(None) is None


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


def test_stability_transition_when_in_regime_transition():
    tj = build_trend_judgment(_minimal_btc(in_regime_transition=True))
    assert tj["stability"] == "transition"


def test_stability_provisional_on_macro_hazard():
    tj = build_trend_judgment(_minimal_btc(macro_hazard=True))
    assert tj["stability"] == "provisional"


def test_consensus_opposing_caps_confidence():
    tj = build_trend_judgment(
        _minimal_btc(confidence=0.82),
        consensus={"direction": "down", "label": "偏空", "score": -0.2, "agreement": 0.7},
    )
    assert tj["confidence"] <= 0.55
    assert tj["consensus_capped"] is True
    assert tj["consensus_misaligned"] is True
    assert tj["consensus_alignment"]["opposing"] is True


def test_consensus_neutral_does_not_cap_uptrend():
    tj = build_trend_judgment(
        _minimal_btc(confidence=0.82),
        consensus={"direction": "neutral", "label": "中性"},
    )
    assert tj["confidence"] == 0.82
    assert tj["consensus_capped"] is False
    assert tj["consensus_misaligned"] is False


def test_consensus_already_low_not_marked_capped():
    conf, misaligned, capped = apply_consensus_confidence_cap(
        0.40,
        {"opposing": True, "aligned": False, "consensus_direction": "down"},
    )
    assert conf == 0.40
    assert misaligned is True
    assert capped is False


def test_hmm_disagreement_lowers_confidence_without_transition():
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
        in_regime_transition=False,
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
    assert meta["disagrees"] is True
    assert meta["reason"] == "trend_disagreement"
    assert updated.confidence <= 0.55
    assert updated.in_regime_transition is False
    assert updated.hmm_disagrees is True
    assert updated.raw_trend == "uptrend"
    assert updated.regime_id == "mid_vol_uptrend"


def test_hmm_low_confidence_caps_without_disagree():
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
    models = {"hmm": {"raw_trend": "uptrend", "confidence": 0.35}}
    updated, meta = apply_hmm_confidence_modifier(analysis, models)
    assert meta["applied"] is True
    assert meta["reason"] == "hmm_low_confidence"
    assert meta["disagrees"] is False
    assert updated.confidence <= 0.60
    assert updated.hmm_disagrees is False


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


def test_hmm_missing_or_error_is_noop():
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
    unchanged, meta = apply_hmm_confidence_modifier(analysis, None)
    assert meta["applied"] is False
    assert unchanged.confidence == 0.80

    err_models = {"hmm": {"error": "timeout", "raw_trend": "downtrend"}}
    unchanged2, meta2 = apply_hmm_confidence_modifier(analysis, err_models)
    assert meta2["applied"] is False
    assert unchanged2.raw_trend == "uptrend"


def test_trend_judgment_no_duplicate_hmm_driver():
    note = "HMM 趋势分歧: 规则=uptrend, HMM=downtrend → 置信度上限 55%"
    tj = build_trend_judgment(
        _minimal_btc(drivers=[note], hmm_disagrees=True),
        hmm_modifier={"applied": True, "disagrees": True, "note": note},
    )
    assert tj["drivers"].count(note) == 1


def test_trend_judgment_hmm_disagrees_flag():
    tj = build_trend_judgment(
        _minimal_btc(hmm_disagrees=True),
        hmm_modifier={"disagrees": True, "applied": True},
    )
    assert tj["hmm_disagrees"] is True


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


def test_business_stance_matrix():
    assert "减仓" in business_stance("uptrend", "fake_breakout_wash")
    assert "谨慎抄底" in business_stance("downtrend", "high_vol_self_heal_range")
    assert "强制观望" in business_stance("uptrend", "macro_frozen_range")
    assert "强制观望" in business_stance("downtrend", "macro_frozen_range")


def test_validate_trend_judgment_contract():
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
    )
    assert validate_trend_judgment(tj) == []


def test_radar_bundle_includes_trend_judgment(monkeypatch):
    from ai_trade_advisor.config import AdvisorConfig
    from ai_trade_advisor.snapshot import bundle as snap_bundle

    cfg = AdvisorConfig(exchange="binance", symbol="BTC/USDT:USDT")

    fake_dashboard = {
        "symbol": cfg.symbol,
        "btc_regime": _minimal_btc(
            hmm_modifier={"applied": True, "disagrees": False, "note": "HMM ok"},
        ),
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
    monkeypatch.setattr(
        "ai_trade_advisor.readiness.get_cached_readiness_tier",
        lambda *a, **k: "demo",
    )

    class _Store:
        def recent(self, **kwargs):
            return []

    result = snap_bundle.build_radar_bundle(cfg, regime_store=_Store())
    assert result.get("trend_judgment") is not None
    assert result["trend_judgment"]["trend"] == "uptrend"
    assert result["readiness_tier"] == "demo"
    assert result["trend_judgment"]["hmm_modifier"]["applied"] is True

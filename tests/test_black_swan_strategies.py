"""黑天鹅实用策略单元测试。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ai_trade_advisor.black_swan.engine import evaluate_black_swan_alert
from ai_trade_advisor.black_swan.strategies import build_practical_signals
from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.features.liquidation_grid import LiquidationGridState
from ai_trade_advisor.features.macro_calendar_engine import MacroHazardState


def _flat_range_df(bars: int = 60, *, base: float = 100_000.0, noise: float = 50.0) -> pd.DataFrame:
    """构造窄幅震荡箱体。"""
    rng = np.random.default_rng(42)
    closes = base + rng.uniform(-noise, noise, size=bars)
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes + noise * 0.3,
            "low": closes - noise * 0.3,
            "close": closes,
            "volume": rng.uniform(80, 120, size=bars),
            "timestamp": np.arange(bars) * 1_800_000,
        }
    )


def test_range_squeeze_watch_after_long_consolidation():
    cfg = AdvisorConfig(bar_minutes=30, black_swan_range_watch_bars=20, black_swan_range_warn_bars=40)
    df = _flat_range_df(65)
    signals = build_practical_signals(df, cfg=cfg)
    squeeze = next(s for s in signals["strategies"] if s["id"] == "range_squeeze")
    assert squeeze["details"]["range_bars"] >= 20
    assert squeeze["level_hint"] >= 1
    assert "箱体驻留" in (squeeze["trigger"] or "")


def test_range_squeeze_combined_with_vol_triggers_warn():
    cfg = AdvisorConfig(bar_minutes=30, black_swan_range_watch_bars=15, black_swan_range_warn_bars=30)
    df = _flat_range_df(55, noise=20.0)
    df["volume"] = 30.0

    signals = build_practical_signals(df, cfg=cfg, microstructure={"oi_change_pct": 3.5}, regime={"raw_trend": "range"})
    alert = evaluate_black_swan_alert(
        macro=MacroHazardState(macro_hazard_flag=False),
        practical_signals=signals,
    )
    assert alert.scores.get("range_squeeze", 0) > 0.5
    assert alert.level >= 1
    assert any("箱体" in t for t in alert.triggers)


def test_funding_extreme_watch():
    signals = build_practical_signals(
        _flat_range_df(30),
        microstructure={"funding_rate": 0.0008},
        cfg=AdvisorConfig(black_swan_funding_extreme_pct=0.0003),
    )
    alert = evaluate_black_swan_alert(
        macro=MacroHazardState(macro_hazard_flag=False),
        practical_signals=signals,
    )
    assert alert.scores.get("funding_extreme", 0) >= 1.0
    assert alert.level >= 1


def test_oi_buildup_in_range_warn():
    signals = build_practical_signals(
        _flat_range_df(40),
        microstructure={"oi_change_pct": 4.0},
        regime={"raw_trend": "range"},
    )
    oi_sig = next(s for s in signals["strategies"] if s["id"] == "oi_divergence")
    assert oi_sig["level_hint"] == 2

    alert = evaluate_black_swan_alert(
        macro=MacroHazardState(macro_hazard_flag=False),
        practical_signals=signals,
    )
    assert alert.level >= 2


def test_liq_proximity_near_pain():
    liq = LiquidationGridState(
        cells=[],
        spot_price=100_000,
        dominant_side="long",
        pain_price=100_800,
        half_life_hours=3,
        total_weight=1_000_000,
    )
    signals = build_practical_signals(_flat_range_df(30), liquidation=liq, price=100_500)
    prox = next(s for s in signals["strategies"] if s["id"] == "liq_proximity")
    assert prox["level_hint"] >= 1

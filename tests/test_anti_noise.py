"""防噪模块单元测试。"""

from __future__ import annotations

import time

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.features.liquidation_grid import LiquidationGrid
from ai_trade_advisor.features.macro_calendar_engine import evaluate_macro_hazard
from ai_trade_advisor.signal.debouncer import apply_advice_cooldown
from ai_trade_advisor.models import TradeAdvice


def test_liquidation_dedupe_and_decay():
    grid = LiquidationGrid(half_life_hours=3.0)
    t0 = time.time() - 3600
    assert grid.ingest("e1", 65000.0, 1000.0, "long", ts=t0)
    assert not grid.ingest("e1", 65000.0, 1000.0, "long", ts=t0)

    snap = grid.snapshot(65000.0, now=time.time())
    assert snap.total_weight > 0
    assert snap.total_weight < 1000.0

    snap2 = grid.snapshot(65000.0, now=time.time())
    assert abs(snap2.total_weight - snap.total_weight) < 1.0


def test_macro_no_false_daily_fallback():
    cfg = AdvisorConfig(coinglass_api_key="")
    state = evaluate_macro_hazard(cfg)
    assert state.macro_hazard_flag is False


def test_cooldown_blocks_flip_keeps_locked_levels():
    key = "test:BTC/USDT"
    long_advice = TradeAdvice(
        bias="long",
        confidence=0.6,
        entry_zone=(100.0, 101.0),
        stop_loss=98.0,
        take_profit=[105.0],
        time_horizon="4h",
        reasoning="long",
        risks=[],
        confluence_score=0.6,
        rule_based=True,
    )
    short_advice = TradeAdvice(
        bias="short",
        confidence=0.7,
        entry_zone=(101.0, 102.0),
        stop_loss=103.0,
        take_profit=[95.0],
        time_horizon="4h",
        reasoning="short",
        risks=[],
        confluence_score=0.7,
        rule_based=True,
    )
    locked, _ = apply_advice_cooldown(long_advice, symbol_key=key, cooldown_sec=900, now=1000.0)
    assert locked.bias == "long"
    assert locked.stop_loss == 98.0

    blocked, state = apply_advice_cooldown(short_advice, symbol_key=key, cooldown_sec=900, now=1100.0)
    assert state.cooldown_active
    assert blocked.bias == "long"
    assert blocked.stop_loss == 98.0

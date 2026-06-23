from __future__ import annotations

from ai_trade_advisor.models import (
    CapitalFlowsSnapshot,
    EtfFlowDay,
    EtfFlowSnapshot,
    ExchangeWalletFlow,
    GexLevel,
    MarketContext,
    SmcSnapshot,
)
from ai_trade_advisor.state_machine.engine import build_quant_state_machine
from ai_trade_advisor.state_machine.routing import resolve_route
from ai_trade_advisor.state_machine.scores import score_flow, score_macro


def _minimal_ctx(**kwargs) -> MarketContext:
    base = MarketContext(
        symbol="BTC/USDT:USDT",
        exchange="okx",
        timeframe="30m",
        as_of="2026-01-01T00:00:00+00:00",
        last_price=100_000.0,
        ohlcv_summary={},
        smc=SmcSnapshot(
            trend="neutral",
            mss_or_choch=None,
            mss_direction=0,
            nearest_ob=None,
            nearest_fvg=None,
        ),
        liquidity_levels=[],
        gex_levels=[],
        orderbook=None,
    )
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def test_resolve_route_gamma_squeeze():
    route = resolve_route(1, 2, -2)
    assert route.diagnosis_id == "gamma_squeeze_rally"
    assert "CTA" in route.system_commands[0]


def test_resolve_route_panic_washout():
    route = resolve_route(0, -2, -2)
    assert route.diagnosis_id == "panic_washout"
    assert any("多头" in c for c in route.system_commands)


def test_resolve_route_matrix_fallback():
    route = resolve_route(0, -2, -2)
    assert route.diagnosis_id == "panic_washout"
    assert route.match_type in ("matrix", "exact")


def test_resolve_route_range_oscillation():
    route = resolve_route(0, 0, 2)
    assert route.diagnosis_id == "range_oscillation"
    assert route.diagnosis == "区间震荡"
    assert route.match_type == "supplemental"


def test_resolve_route_indeterminate():
    route = resolve_route(0, 0, 0)
    assert route.diagnosis_id == "indeterminate"
    assert route.diagnosis == "不明确"


def test_score_macro_uptrend_positive():
    ctx = _minimal_ctx(
        btc_regime={"raw_trend": "uptrend"},
        capital_flows=CapitalFlowsSnapshot(
            btc_etf=EtfFlowSnapshot(
                asset="BTC",
                total_7d_usd=80_000_000,
                latest=EtfFlowDay(date="2026-01-01", flow_usd=10_000_000),
            )
        ),
    )
    score, drivers = score_macro(ctx)
    assert score == 1
    assert drivers


def test_score_flow_extreme_outflow():
    ctx = _minimal_ctx(
        capital_flows=CapitalFlowsSnapshot(
            btc_etf=EtfFlowSnapshot(
                asset="BTC",
                latest=EtfFlowDay(date="2026-01-01", flow_usd=-150_000_000),
            ),
            btc_exchange_wallet=ExchangeWalletFlow(
                asset="BTC",
                net_to_exchange_1d=500.0,
                net_to_exchange_7d=None,
                net_to_exchange_30d=None,
            ),
        ),
    )
    score, _ = score_flow(ctx)
    assert score <= -1


def test_build_quant_state_machine_snapshot():
    ctx = _minimal_ctx(
        btc_regime={"raw_trend": "uptrend", "spot_cvd_breakout": True},
        gex_levels=[
            GexLevel(price=102_000, gex_notional_proxy=1000, level_type="resistance"),
            GexLevel(price=98_000, gex_notional_proxy=800, level_type="support"),
        ],
        vol_ratio=0.25,
    )
    snap = build_quant_state_machine(ctx)
    assert len(snap.score_vector) == 3
    assert snap.diagnosis
    assert snap.okx_strategy is not None
    assert snap.okx_strategy.grid.direction in ("long", "short", "neutral", "single")
    assert snap.weekly_policy.cta_mode in ("enhanced", "standard", "defensive")
    d = snap.to_dict()
    assert d["score_label"].startswith("$Macro=")
    assert d["okx_strategy"]["grid"]["grid_count"] >= 6


def test_okx_strategy_range_oscillation():
    from ai_trade_advisor.state_machine.okx_strategies import build_okx_strategy_plan
    from ai_trade_advisor.state_machine.routing import RouteResult, WeeklyPolicy

    route = RouteResult("range_oscillation", "区间震荡", [])
    policy = WeeklyPolicy(12.0, "", "standard", "full_open")
    plan = build_okx_strategy_plan(
        route,
        spot=100_000.0,
        boundaries={"lower_price": 97_500, "upper_price": 102_500, "range_pct": 5.0},
        weekly_policy=policy,
    )
    assert plan.grid.enabled
    assert plan.grid.direction == "neutral"
    assert plan.grid.direction_label == "双向"
    assert plan.martingale.enabled is False


def test_okx_strategy_gamma_squeeze_disables_grid():
    from ai_trade_advisor.state_machine.okx_strategies import build_okx_strategy_plan
    from ai_trade_advisor.state_machine.routing import RouteResult, WeeklyPolicy

    route = RouteResult("gamma_squeeze_rally", "狂暴拉升市", [])
    policy = WeeklyPolicy(18.0, "", "enhanced", "pause")
    plan = build_okx_strategy_plan(
        route,
        spot=100_000.0,
        boundaries={},
        weekly_policy=policy,
    )
    assert plan.grid.enabled is False
    assert plan.martingale.enabled is False
    assert plan.primary_tool == "trend_cta"

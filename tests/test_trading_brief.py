from __future__ import annotations

import pandas as pd

from ai_trade_advisor.features.chart_payload import build_chart_payload
from ai_trade_advisor.features.trading_brief import build_trading_brief
from ai_trade_advisor.models import (
    GexLevel,
    LiquidityLevel,
    MarketContext,
    PriceZone,
    SmcSnapshot,
    TradeAdvice,
)


def _sample_df(n: int = 30) -> pd.DataFrame:
    rows = []
    price = 97000.0
    for i in range(n):
        o = price
        c = price + (i % 3 - 1) * 50
        rows.append(
            {
                "datetime": pd.Timestamp("2026-06-01") + pd.Timedelta(hours=i),
                "open": o,
                "high": max(o, c) + 80,
                "low": min(o, c) - 80,
                "close": c,
                "volume": 1000 + i,
            }
        )
        price = c
    return pd.DataFrame(rows)


def _ctx() -> MarketContext:
    return MarketContext(
        symbol="BTC/USDT:USDT",
        exchange="okx",
        timeframe="30m",
        as_of="2026-06-23T00:00:00Z",
        last_price=97200.0,
        ohlcv_summary={"range_20bar_high": 98500.0, "range_20bar_low": 95800.0},
        smc=SmcSnapshot(
            trend="bullish",
            mss_or_choch="CHoCH",
            mss_direction=1,
            nearest_ob=PriceZone(low=96800, high=97200, label="OB"),
            nearest_fvg=None,
        ),
        liquidity_levels=[
            LiquidityLevel(price=96500, side="sell_side", swept=True, strength=1.2),
            LiquidityLevel(price=95800, side="sell_side", swept=False, strength=0.9),
        ],
        gex_levels=[
            GexLevel(price=97000, gex_notional_proxy=4e6, level_type="magnet"),
            GexLevel(price=98500, gex_notional_proxy=2e6, level_type="resistance"),
        ],
        orderbook=None,
        btc_regime={"oi_change_pct": 1.2, "funding_rate": 0.0001, "cvd_trend": "bullish", "spot_cvd_breakout": True},
        pipeline={
            "layers": {
                "ingestion": {
                    "microstructure": {
                        "oi_change_pct": 1.2,
                        "funding_rate": 0.0001,
                        "cvd_trend": "bullish",
                    }
                }
            }
        },
    )


def _advice() -> TradeAdvice:
    return TradeAdvice(
        bias="long",
        confidence=0.68,
        confluence_score=0.71,
        reasoning="Bullish structure with CVD confirmation.",
        entry_zone=(96800.0, 97200.0),
        stop_loss=96200.0,
        take_profit=[98200.0, 99100.0],
        risks=["宏观事件窗口"],
        time_horizon="1h-4h",
        rule_based=True,
    )


def test_build_chart_payload_bars_and_overlays():
    ctx = _ctx()
    payload = build_chart_payload(_sample_df(), {"ticker": {"change_pct_24h": 1.5}}, ctx, max_bars=20)
    assert payload["timeframe"] == "30m"
    assert len(payload["bars"]) == 20
    assert payload["bars"][-1]["c"] > 0
    kinds = {o["kind"] for o in payload["overlays"]}
    assert "kama" in kinds
    assert "liquidity" in kinds
    assert "gex" in kinds
    assert payload["last_price"] == 97200.0


def test_build_trading_brief_aggregates_signals():
    brief = build_trading_brief(_ctx(), _advice())
    assert brief["bias"] == "long"
    assert brief["horizon"] == "1h-4h"
    assert "CHoCH" in brief["smc_action"]
    assert "95800" in brief["liquidity_note"]
    assert brief["ai_mode"] == "rule_based"
    assert len(brief["operation_plan"]) >= 3
    assert "现货 CVD 突破确认" in brief["catalysts"]
    assert brief["derivatives"]["cvd_trend"] == "bullish"


def test_build_chart_payload_empty_df():
    ctx = _ctx()
    payload = build_chart_payload(pd.DataFrame(), {}, ctx)
    assert payload["bars"] == []

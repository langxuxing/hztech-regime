"""事件分析引擎单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.ticker import LiveTickerSnapshot
from ai_trade_advisor.bigevent.engine import (
    _merge_events,
    fetch_btc_price,
    is_demo_event,
)
from ai_trade_advisor.bigevent.impact_analyzer import analyze_event_impact, analyze_events
from ai_trade_advisor.bigevent.models import MarketEvent


def _event(
    *,
    eid: str = "e1",
    title: str = "Test",
    category: str = "breaking",
    source: str = "coinglass",
    importance: int = 3,
    btc_relevance: float = 0.8,
    tags: list[str] | None = None,
) -> MarketEvent:
    return MarketEvent(
        id=eid,
        title=title,
        summary=title,
        category=category,  # type: ignore[arg-type]
        source=source,
        published_at="2026-06-21T12:00:00+00:00",
        importance=importance,
        btc_relevance=btc_relevance,
        tags=tags or [],
    )


class TestEventHelpers(unittest.TestCase):
    def test_is_demo_event(self) -> None:
        demo = _event(source="x:demo", tags=["x", "demo"])
        real = _event(source="x:@whale_alert")
        self.assertTrue(is_demo_event(demo))
        self.assertFalse(is_demo_event(real))

    def test_merge_events_dedupes_by_id(self) -> None:
        a = _event(eid="same", title="A")
        b = _event(eid="same", title="B")
        c = _event(eid="other", title="C")
        merged = _merge_events([a, b], [c])
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].title, "A")


class TestImpactAnalyzer(unittest.TestCase):
    def test_regulatory_approval_not_auto_bearish(self) -> None:
        event = _event(
            title="SEC approves spot Bitcoin ETF application",
            category="regulatory",
            source="coinglass:news",
        )
        impact = analyze_event_impact(event, btc_price=90000.0)
        self.assertIn(impact.direction, ("bullish", "neutral", "uncertain"))
        self.assertGreaterEqual(impact.impact_score, -0.1)

    def test_regulatory_lawsuit_stays_bearish(self) -> None:
        event = _event(
            title="SEC files lawsuit against crypto exchange",
            category="regulatory",
            source="coinglass:news",
        )
        impact = analyze_event_impact(event, btc_price=90000.0)
        self.assertLess(impact.impact_score, 0)

    def test_llm_budget_limits_calls(self) -> None:
        cfg = AdvisorConfig(ai_api_key="test-key", event_llm_max_calls=1)
        events = [
            _event(eid="1", title="BREAKING Fed rate cut", importance=5, category="macro"),
            _event(eid="2", title="SEC approves ETF", importance=5, category="regulatory"),
        ]
        with patch("ai_trade_advisor.bigevent.impact_analyzer._try_llm_impact", return_value="LLM") as mock_llm:
            analyze_events(events, btc_price=90000.0, cfg=cfg)
        self.assertEqual(mock_llm.call_count, 1)


class TestBtcPrice(unittest.TestCase):
    def test_fetch_btc_price_uses_btc_symbol(self) -> None:
        cfg = AdvisorConfig(exchange="binance", symbol="ETH/USDT:USDT")
        snap = LiveTickerSnapshot(
            last=64000.0,
            change_pct_24h=1.0,
            as_of="2026-06-22T14:00:00+00:00",
        )

        with patch("ai_trade_advisor.datasource.ticker.fetch_live_ticker", return_value=snap) as mock_ticker:
            price = fetch_btc_price(cfg)

        mock_ticker.assert_called_once()
        called_cfg = mock_ticker.call_args[0][0]
        self.assertEqual(called_cfg.symbol, "BTC/USDT:USDT")
        self.assertEqual(called_cfg.exchange, "binance")
        self.assertEqual(price, 64000.0)


if __name__ == "__main__":
    unittest.main()

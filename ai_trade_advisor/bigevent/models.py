from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EventCategory = Literal[
    "macro",
    "exchange",
    "breaking",
    "regulatory",
    "liquidation",
    "listing",
    "maintenance",
    "other",
]
ImpactLevel = Literal["critical", "high", "medium", "low", "negligible"]
VolatilityExpectation = Literal["extreme", "high", "normal", "low"]


@dataclass
class MarketEvent:
    """统一事件模型，聚合日历 / 交易所 / X 来源。"""

    id: str
    title: str
    summary: str
    category: EventCategory
    source: str
    published_at: str
    importance: int = 3
    btc_relevance: float = 0.5
    tags: list[str] = field(default_factory=list)
    source_url: str | None = None
    country: str | None = None
    scheduled_at: str | None = None
    is_scheduled: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "category": self.category,
            "source": self.source,
            "published_at": self.published_at,
            "importance": self.importance,
            "btc_relevance": round(self.btc_relevance, 3),
            "tags": self.tags,
            "source_url": self.source_url,
            "country": self.country,
            "scheduled_at": self.scheduled_at,
            "is_scheduled": self.is_scheduled,
        }


@dataclass
class EventImpact:
    """单条事件的 BTC 影响分析。"""

    event_id: str
    impact_score: float
    impact_level: ImpactLevel
    direction: Literal["bullish", "bearish", "neutral", "uncertain"]
    expected_volatility: VolatilityExpectation
    reasoning: str
    btc_price: float | None = None
    confidence: float = 0.5
    actionable: bool = False
    time_horizon: str = "intraday"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "impact_score": round(self.impact_score, 3),
            "impact_level": self.impact_level,
            "direction": self.direction,
            "expected_volatility": self.expected_volatility,
            "reasoning": self.reasoning,
            "btc_price": self.btc_price,
            "confidence": round(self.confidence, 3),
            "actionable": self.actionable,
            "time_horizon": self.time_horizon,
        }


@dataclass
class EventAnalysisSnapshot:
    """一次扫描的完整输出。"""

    as_of: str
    btc_price: float | None
    calendar_events: list[MarketEvent] = field(default_factory=list)
    breaking_events: list[MarketEvent] = field(default_factory=list)
    impacts: list[EventImpact] = field(default_factory=list)
    upcoming_high_impact: list[MarketEvent] = field(default_factory=list)
    data_quality: str = "partial"
    notes: list[str] = field(default_factory=list)
    scan_duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        impact_by_id = {i.event_id: i for i in self.impacts}
        return {
            "as_of": self.as_of,
            "btc_price": self.btc_price,
            "data_quality": self.data_quality,
            "notes": self.notes,
            "scan_duration_ms": self.scan_duration_ms,
            "calendar_events": [e.to_dict() for e in self.calendar_events],
            "breaking_events": [e.to_dict() for e in self.breaking_events],
            "upcoming_high_impact": [e.to_dict() for e in self.upcoming_high_impact],
            "impacts": [i.to_dict() for i in self.impacts],
            "analyzed_events": [
                {**e.to_dict(), "impact": impact_by_id[e.id].to_dict()}
                for e in (*self.breaking_events, *self.calendar_events)
                if e.id in impact_by_id
            ],
            "summary": _build_summary(self),
        }


def _build_summary(snap: EventAnalysisSnapshot) -> dict[str, Any]:
    critical = [i for i in snap.impacts if i.impact_level in ("critical", "high")]
    bullish = [i for i in critical if i.direction == "bullish"]
    bearish = [i for i in critical if i.direction == "bearish"]
    return {
        "total_calendar": len(snap.calendar_events),
        "total_breaking": len(snap.breaking_events),
        "high_impact_count": len(critical),
        "bullish_signals": len(bullish),
        "bearish_signals": len(bearish),
        "upcoming_macro": len(snap.upcoming_high_impact),
        "overall_risk": _overall_risk(snap),
    }


def _overall_risk(snap: EventAnalysisSnapshot) -> str:
    high = [i for i in snap.impacts if i.impact_level in ("critical", "high")]
    if not high:
        return "low"
    bearish = sum(1 for i in high if i.direction == "bearish")
    bullish = sum(1 for i in high if i.direction == "bullish")
    vol_extreme = any(i.expected_volatility == "extreme" for i in high)
    if vol_extreme or len(high) >= 3:
        return "elevated"
    if bearish > bullish + 1:
        return "bearish"
    if bullish > bearish + 1:
        return "bullish"
    return "mixed"

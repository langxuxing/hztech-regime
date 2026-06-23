"""合并 board 事件与 bigevent 为统一列表。"""

from __future__ import annotations

from typing import Any

from ai_trade_advisor.bigevent.models import MarketEvent
from ai_trade_advisor.models import MajorEvent


def build_unified_events(
    major_events: list[MajorEvent],
    upcoming: list[MarketEvent] | None = None,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    def add(item: dict[str, Any]) -> None:
        key = item.get("id") or item.get("title", "")
        if not key or key in seen:
            return
        seen.add(str(key))
        out.append(item)

    for e in major_events:
        if e.title == "暂无重大事件":
            continue
        add(
            {
                "id": e.id,
                "title": e.title,
                "description": e.description,
                "category": e.category,
                "severity": e.severity,
                "impact": e.impact,
                "timestamp": e.timestamp,
                "source": "board",
            }
        )

    for e in upcoming or []:
        add(
            {
                "id": f"up-{e.id}",
                "title": e.title,
                "description": e.summary,
                "category": e.category,
                "severity": "high" if e.importance >= 4 else "medium",
                "impact": "neutral",
                "timestamp": e.scheduled_at or e.published_at,
                "source": e.source,
                "is_upcoming": True,
            }
        )

    return out

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.coinglass_calendar import fetch_coinglass_calendar

_MACRO_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("CPI", re.compile(r"\bcpi\b|consumer price|消费者物价", re.I)),
    ("FOMC", re.compile(r"\bfomc\b|fed interest|利率决议|powell|联邦基金", re.I)),
    ("NFP", re.compile(r"\bnfp\b|nonfarm|non-farm|非农就业|非农", re.I)),
]


@dataclass
class MacroHazardState:
    macro_hazard_flag: bool
    active_events: list[str] = field(default_factory=list)
    next_event: str | None = None
    minutes_to_next: int | None = None
    window_minutes: int = 120
    as_of: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "macro_hazard_flag": self.macro_hazard_flag,
            "active_events": self.active_events,
            "next_event": self.next_event,
            "minutes_to_next": self.minutes_to_next,
            "window_minutes": self.window_minutes,
            "as_of": self.as_of,
        }


def evaluate_macro_hazard(
    cfg: AdvisorConfig | None = None,
    *,
    now: datetime | None = None,
) -> MacroHazardState:
    """
    宏观熔断：CPI / FOMC / NFP 公布前后 ±N 分钟 → macro_hazard_flag=True。
    仅依赖 CoinGlass 日历中匹配到的真实宏观事件，无日历时不做假窗口兜底。
    """
    cfg = cfg or AdvisorConfig.from_env()
    now = now or datetime.now(timezone.utc)
    window_min = max(1, cfg.macro_hazard_window_min)

    scheduled = _load_scheduled_events(cfg, now)
    active: list[str] = []
    next_event: str | None = None
    next_delta: int | None = None

    for title, event_time in scheduled:
        delta_min = int((event_time - now).total_seconds() / 60)
        if abs(delta_min) <= window_min:
            active.append(f"{title} ({delta_min:+d}min)")
        if event_time >= now and (next_delta is None or delta_min < next_delta):
            next_event = title
            next_delta = delta_min

    return MacroHazardState(
        macro_hazard_flag=len(active) > 0,
        active_events=active,
        next_event=next_event,
        minutes_to_next=next_delta,
        window_minutes=window_min,
        as_of=now.isoformat(),
    )


def _load_scheduled_events(
    cfg: AdvisorConfig,
    now: datetime,
) -> list[tuple[str, datetime]]:
    out: list[tuple[str, datetime]] = []
    try:
        for ev in fetch_coinglass_calendar(cfg):
            if ev.category != "macro" and "macro" not in (ev.tags or []):
                title = ev.title or ""
                if not _match_macro(title):
                    continue
            title = ev.title or "macro"
            if not _match_macro(title):
                continue
            ts = ev.scheduled_at or ev.published_at
            if not ts:
                continue
            dt = _parse_iso(ts)
            if dt is None:
                continue
            if abs((dt - now).total_seconds()) > timedelta(days=2).total_seconds():
                continue
            out.append((title, dt))
    except Exception:
        pass
    return out


def _match_macro(title: str) -> bool:
    return any(p.search(title) for _, p in _MACRO_PATTERNS)


def _parse_iso(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

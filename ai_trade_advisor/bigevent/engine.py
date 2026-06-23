from __future__ import annotations

import time
from datetime import datetime, timezone

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.coinglass_calendar import fetch_coinglass_calendar
from ai_trade_advisor.datasource.exchange_events import fetch_exchange_events
from ai_trade_advisor.bigevent.impact_analyzer import analyze_events
from ai_trade_advisor.bigevent.models import EventAnalysisSnapshot, MarketEvent
from ai_trade_advisor.bigevent.store import EventStore
from ai_trade_advisor.datasource.x_monitor import fetch_x_breaking

BTC_SYMBOL = "BTC/USDT:USDT"


def is_demo_event(event: MarketEvent) -> bool:
    source = event.source.lower()
    return source == "x:demo" or ":demo" in source or "demo" in event.tags


def run_event_analysis(
    cfg: AdvisorConfig,
    *,
    store: EventStore | None = None,
    skip_x: bool = False,
    skip_exchange: bool = False,
    skip_calendar: bool = False,
) -> EventAnalysisSnapshot:
    """运行完整事件扫描：日历 + 交易所 + X → 影响分析。"""
    t0 = time.perf_counter()
    notes: list[str] = []
    store = store or EventStore()

    btc_price = fetch_btc_price(cfg)

    calendar_events: list[MarketEvent] = []
    if not skip_calendar:
        calendar_events = fetch_coinglass_calendar(cfg)
        if not calendar_events and not cfg.coinglass_api_key:
            notes.append("未配置 COINGLASS_API_KEY，日历使用网页抓取兜底")
        elif calendar_events:
            notes.append(f"CoinGlass 日历/新闻 {len(calendar_events)} 条")

    exchange_events: list[MarketEvent] = []
    if not skip_exchange:
        exchange_events = fetch_exchange_events()
        btc_related = [e for e in exchange_events if e.btc_relevance >= 0.5]
        if btc_related:
            calendar_events.extend(btc_related)
        notes.append(
            f"交易所公告 {len(exchange_events)} 条（BTC相关 {len(btc_related)}）"
        )

    breaking_events: list[MarketEvent] = []
    if not skip_x:
        breaking_events = fetch_x_breaking(cfg)
        demo_breaking = [e for e in breaking_events if is_demo_event(e)]
        if not cfg.x_bearer_token:
            if cfg.event_demo_mode and demo_breaking:
                notes.append("X 监控：演示模式（配置 X_BEARER_TOKEN 启用实时）")
            else:
                notes.append("未配置 X_BEARER_TOKEN，跳过 X 监控")
                breaking_events = [e for e in breaking_events if not is_demo_event(e)]
        else:
            notes.append(f"X 突发 {len(breaking_events)} 条")

    all_events = _merge_events(calendar_events, breaking_events)
    persistable = [e for e in all_events if not is_demo_event(e)]
    new_count = store.upsert_events(persistable)

    impacts = analyze_events(all_events, btc_price=btc_price, cfg=cfg)
    store.save_impacts([i for i in impacts if not _is_demo_impact(i.event_id, all_events)])

    upcoming = _upcoming_high_impact(calendar_events)
    quality = _data_quality(cfg, breaking_events, calendar_events)

    elapsed = int((time.perf_counter() - t0) * 1000)
    notes.append(f"新增事件 {new_count}，库内共 {store.count()} 条，耗时 {elapsed}ms")

    return EventAnalysisSnapshot(
        as_of=datetime.now(timezone.utc).isoformat(),
        btc_price=btc_price,
        calendar_events=sorted(calendar_events, key=_event_time, reverse=True)[:50],
        breaking_events=sorted(breaking_events, key=_event_time, reverse=True)[:30],
        impacts=impacts,
        upcoming_high_impact=upcoming[:10],
        data_quality=quality,
        notes=notes,
        scan_duration_ms=elapsed,
    )


def fetch_btc_price(cfg: AdvisorConfig) -> float | None:
    """始终拉取 BTC 永续价格，不受 cfg.symbol 影响。"""
    try:
        from ai_trade_advisor.datasource.ticker import fetch_live_ticker

        snap = fetch_live_ticker(
            AdvisorConfig(
                exchange=cfg.exchange,
                symbol=BTC_SYMBOL,
            )
        )
        return snap.last
    except Exception:
        return None


def _data_quality(
    cfg: AdvisorConfig,
    breaking: list[MarketEvent],
    calendar: list[MarketEvent],
) -> str:
    has_demo = any(is_demo_event(e) for e in breaking)
    has_real = any(not is_demo_event(e) for e in (*breaking, *calendar))
    if cfg.coinglass_api_key and cfg.x_bearer_token and has_real:
        return "good"
    if has_demo and not has_real:
        return "demo"
    if cfg.coinglass_api_key or cfg.x_bearer_token:
        return "partial"
    return "demo" if has_demo else "partial"


def _is_demo_impact(event_id: str, events: list[MarketEvent]) -> bool:
    by_id = {e.id: e for e in events}
    event = by_id.get(event_id)
    return event is not None and is_demo_event(event)


def _merge_events(*groups: list[MarketEvent]) -> list[MarketEvent]:
    seen: set[str] = set()
    out: list[MarketEvent] = []
    for group in groups:
        for e in group:
            if e.id in seen:
                continue
            seen.add(e.id)
            out.append(e)
    return out


def load_pipeline_event_context(
    store: EventStore | None = None,
) -> tuple[int, list[MarketEvent]]:
    """轻量读取缓存事件，供主流水线 event_risk / unified_events 使用。"""
    store = store or EventStore()
    recent = store.recent_events(limit=80)
    calendar_like = [
        e for e in recent if e.is_scheduled or e.importance >= 4 or e.category == "macro"
    ]
    upcoming = _upcoming_high_impact(calendar_like)
    return len(upcoming), upcoming


def _upcoming_high_impact(events: list[MarketEvent]) -> list[MarketEvent]:
    now = datetime.now(timezone.utc)
    upcoming: list[MarketEvent] = []
    for e in events:
        if not e.is_scheduled or e.importance < 3:
            continue
        if e.btc_relevance < 0.4:
            continue
        ts = e.scheduled_at or e.published_at
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt >= now:
                upcoming.append(e)
        except ValueError:
            continue
    upcoming.sort(key=lambda x: x.scheduled_at or x.published_at)
    return upcoming


def _event_time(e: MarketEvent) -> str:
    return e.published_at or ""

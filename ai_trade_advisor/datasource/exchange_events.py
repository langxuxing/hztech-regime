from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

import requests

from ai_trade_advisor.bigevent.models import MarketEvent

BINANCE_CMS = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
OKX_ANNOUNCE = "https://www.okx.com/api/v5/support/announcements"
BYBIT_ANNOUNCE = "https://api.bybit.com/v5/announcements/index"

EXCHANGE_KEYWORDS = (
    "btc", "bitcoin", "listing", "delist", "maintenance", "suspend", "resume",
    "perpetual", "futures", "margin", "halving", "etf",
    "比特币", "上线", "下架", "维护", "暂停", "恢复", "合约",
)


def fetch_exchange_events() -> list[MarketEvent]:
    """抓取主流交易所公告（Binance / OKX / Bybit 公开 API）。"""
    events: list[MarketEvent] = []
    for fetcher in (_fetch_binance, _fetch_okx, _fetch_bybit):
        try:
            events.extend(fetcher())
        except Exception:
            continue
    return _dedupe_by_title(events)


def _fetch_binance() -> list[MarketEvent]:
    resp = requests.get(
        BINANCE_CMS,
        params={"type": 1, "pageNo": 1, "pageSize": 20},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    articles = (payload.get("data") or {}).get("catalogs") or []
    if not articles:
        articles = payload.get("data") or []
    rows: list[dict] = []
    if isinstance(articles, list):
        for cat in articles:
            if isinstance(cat, dict) and cat.get("articles"):
                rows.extend(cat["articles"])
    return [_binance_row(r) for r in rows if isinstance(r, dict) and str(r.get("title") or "").strip()]


def _binance_row(row: dict[str, Any]) -> MarketEvent:
    title = str(row.get("title") or "").strip()
    code = row.get("code") or row.get("id") or ""
    ts = row.get("releaseDate") or row.get("publishDate")
    pub = _ms_to_iso(ts)
    url = f"https://www.binance.com/en/support/announcement/{code}" if code else None
    text = title.lower()
    return MarketEvent(
        id=_event_id("binance", title, pub),
        title=title,
        summary=str(row.get("brief") or title)[:300],
        category=_exchange_category(text),
        source="binance",
        published_at=pub,
        importance=_exchange_importance(text),
        btc_relevance=_exchange_btc_relevance(text),
        tags=["exchange", "binance"],
        source_url=url,
        raw=row,
    )


def _fetch_okx() -> list[MarketEvent]:
    resp = requests.get(
        OKX_ANNOUNCE,
        params={"page": "1"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json().get("data") or []
    rows = data[0].get("details") if data and isinstance(data[0], dict) else []
    if not isinstance(rows, list):
        return []
    out: list[MarketEvent] = []
    for row in rows[:25]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        ts = row.get("pTime") or row.get("timestamp")
        pub = _ms_to_iso(ts)
        url = row.get("url") or f"https://www.okx.com/help/{row.get('id', '')}"
        text = title.lower()
        out.append(
            MarketEvent(
                id=_event_id("okx", title, pub),
                title=title,
                summary=title,
                category=_exchange_category(text),
                source="okx",
                published_at=pub,
                importance=_exchange_importance(text),
                btc_relevance=_exchange_btc_relevance(text),
                tags=["exchange", "okx"],
                source_url=url,
                raw=row,
            )
        )
    return out


def _fetch_bybit() -> list[MarketEvent]:
    resp = requests.get(
        BYBIT_ANNOUNCE,
        params={"locale": "en-US", "limit": 20},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    resp.raise_for_status()
    rows = (resp.json().get("result") or {}).get("list") or []
    out: list[MarketEvent] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        ts = row.get("dateTimestamp") or row.get("publishTime")
        pub = _ms_to_iso(ts)
        url = row.get("url")
        text = title.lower()
        out.append(
            MarketEvent(
                id=_event_id("bybit", title, pub),
                title=title,
                summary=title,
                category=_exchange_category(text),
                source="bybit",
                published_at=pub,
                importance=_exchange_importance(text),
                btc_relevance=_exchange_btc_relevance(text),
                tags=["exchange", "bybit"],
                source_url=url,
                raw=row,
            )
        )
    return out


def _exchange_category(text: str) -> str:
    if any(k in text for k in ("maintenance", "upgrade", "suspend", "维护", "升级", "暂停")):
        return "maintenance"
    if any(k in text for k in ("list", "delist", "上线", "下架", "listing")):
        return "listing"
    return "exchange"


def _exchange_importance(text: str) -> int:
    score = 2
    if any(k in text for k in ("btc", "bitcoin", "比特币")):
        score += 2
    if any(k in text for k in ("all", "system", "maintenance", "全站", "系统")):
        score += 1
    if any(k in text for k in ("delist", "下架", "suspend trading")):
        score += 1
    return min(score, 5)


def _exchange_btc_relevance(text: str) -> float:
    if any(k in text for k in ("btc", "bitcoin", "比特币")):
        return 0.85
    if any(k in text for k in ("usdt", "usd", "perpetual", "futures")):
        return 0.45
    return 0.2


def _dedupe_by_title(events: list[MarketEvent]) -> list[MarketEvent]:
    seen: set[str] = set()
    out: list[MarketEvent] = []
    for e in events:
        key = re.sub(r"\s+", " ", e.title.lower().strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def _ms_to_iso(ms: Any) -> str:
    try:
        val = int(ms)
        if val > 1_000_000_000_000:
            val //= 1000
        return datetime.fromtimestamp(val, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc).isoformat()


def _event_id(prefix: str, title: str, ts: str) -> str:
    return hashlib.sha256(f"{prefix}|{title}|{ts}".encode()).hexdigest()[:16]

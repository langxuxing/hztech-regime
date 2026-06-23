from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.fund_flow import _coinglass_get
from ai_trade_advisor.bigevent.models import MarketEvent

COINGLASS_CALENDAR_URL = "https://www.coinglass.com/calendar"

# 高影响宏观关键词（中英文）
MACRO_HIGH_KEYWORDS = (
    "cpi", "fomc", "fed", "interest rate", "nonfarm", "nfp", "gdp", "ppi",
    "unemployment", "inflation", "powell", "ecb", "boj", "pmi",
    "消费者物价", "非农", "利率决议", "通胀", "gdp",
)


def fetch_coinglass_calendar(cfg: AdvisorConfig, *, language: str = "zh") -> list[MarketEvent]:
    """CoinGlass 经济日历（API 优先；无 Key 时不使用低质量 HTML 兜底）。"""
    events: list[MarketEvent] = []
    if cfg.coinglass_api_key:
        events.extend(_fetch_economic_api(cfg, language=language))
        events.extend(_fetch_coinglass_news(cfg, language=language))
    elif cfg.allow_coinglass_scrape_fallback:
        events.extend(_scrape_coinglass_calendar())
    return events


def _fetch_economic_api(cfg: AdvisorConfig, *, language: str) -> list[MarketEvent]:
    now = datetime.now(timezone.utc)
    start = int((now - timedelta(days=3)).timestamp() * 1000)
    end = int((now + timedelta(days=7)).timestamp() * 1000)
    try:
        rows = _coinglass_get(
            cfg,
            "/api/calendar/economic-data",
            {"start_time": start, "end_time": end, "language": language},
        )
    except Exception:
        return []
    if not isinstance(rows, list):
        return []

    out: list[MarketEvent] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("calendar_name") or "").strip()
        if not name:
            continue
        ts = row.get("publish_timestamp")
        pub = _ms_to_iso(ts) if ts else now.isoformat()
        importance = int(row.get("importance_level") or 1)
        country = str(row.get("country_name") or row.get("country_code") or "")
        effect = str(row.get("data_effect") or "")
        forecast = str(row.get("forecast_value") or "")
        previous = str(row.get("previous_value") or "")
        published = str(row.get("published_value") or "")

        summary_parts = [p for p in (country, effect, f"预期 {forecast}" if forecast else "", f"前值 {previous}" if previous else "", f"公布 {published}" if published else "") if p]
        summary = " | ".join(summary_parts) or name

        btc_rel = _macro_btc_relevance(name, importance)
        tags = _macro_tags(name, country)
        eid = _event_id("coinglass:calendar", name, pub)

        out.append(
            MarketEvent(
                id=eid,
                title=name,
                summary=summary,
                category="macro",
                source="coinglass",
                published_at=pub,
                importance=min(importance + 1, 5),
                btc_relevance=btc_rel,
                tags=tags,
                source_url="https://www.coinglass.com/calendar",
                country=country or None,
                scheduled_at=pub,
                is_scheduled=not published,
                raw=row,
            )
        )
    return out


def _fetch_coinglass_news(cfg: AdvisorConfig, *, language: str) -> list[MarketEvent]:
    now = datetime.now(timezone.utc)
    start = int((now - timedelta(hours=24)).timestamp() * 1000)
    try:
        rows = _coinglass_get(
            cfg,
            "/api/article/list",
            {"start_time": start, "language": language, "page": 1, "per_page": 30},
        )
    except Exception:
        return []
    if not isinstance(rows, list):
        return []

    out: list[MarketEvent] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = _strip_html(str(row.get("article_title") or "")).strip()
        if not title:
            continue
        desc = _strip_html(str(row.get("article_description") or row.get("article_content") or ""))[:400]
        ts = row.get("article_release_time")
        pub = _ms_to_iso(ts) if ts else now.isoformat()
        source_name = str(row.get("source_name") or "coinglass")
        text = f"{title} {desc}".lower()
        category = _news_category(text)
        importance = _news_importance(text)
        btc_rel = _news_btc_relevance(text)

        out.append(
            MarketEvent(
                id=_event_id("coinglass:news", title, pub),
                title=title,
                summary=desc or title,
                category=category,
                source=f"coinglass:{source_name.lower()}",
                published_at=pub,
                importance=importance,
                btc_relevance=btc_rel,
                tags=_news_tags(text),
                source_url=None,
                raw=row,
            )
        )
    return out


def _scrape_coinglass_calendar() -> list[MarketEvent]:
    """CoinGlass 日历页 HTML 抓取（无 API Key 时兜底）。"""
    try:
        from bs4 import BeautifulSoup
        import requests

        resp = requests.get(
            COINGLASS_CALENDAR_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RegimeTrend/1.0)"},
            timeout=20,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return []

    events: list[MarketEvent] = []
    now = datetime.now(timezone.utc).isoformat()
    # 页面结构可能变化：抓取含宏观关键词的文本块
    for node in soup.find_all(["div", "tr", "li", "span"]):
        text = node.get_text(" ", strip=True)
        if len(text) < 8 or len(text) > 200:
            continue
        lower = text.lower()
        if not any(k in lower for k in MACRO_HIGH_KEYWORDS):
            continue
        if text in {e.title for e in events}:
            continue
        events.append(
            MarketEvent(
                id=_event_id("coinglass:scrape", text, now),
                title=text[:120],
                summary="CoinGlass 日历页抓取",
                category="macro",
                source="coinglass:scrape",
                published_at=now,
                importance=3,
                btc_relevance=_macro_btc_relevance(text, 2),
                tags=["macro", "scraped"],
                source_url=COINGLASS_CALENDAR_URL,
                is_scheduled=True,
            )
        )
        if len(events) >= 20:
            break
    return events


def _macro_btc_relevance(name: str, importance: int) -> float:
    lower = name.lower()
    score = 0.35 + importance * 0.12
    if any(k in lower for k in ("cpi", "fomc", "fed", "interest", "nonfarm", "非农", "利率", "通胀")):
        score += 0.25
    if any(k in lower for k in ("gdp", "unemployment", "pmi")):
        score += 0.1
    return min(score, 1.0)


def _macro_tags(name: str, country: str) -> list[str]:
    tags = ["macro"]
    if country:
        tags.append(country.lower())
    lower = name.lower()
    for kw in ("cpi", "fomc", "fed", "nfp", "gdp", "ppi"):
        if kw in lower:
            tags.append(kw)
    return tags


def _news_category(text: str) -> str:
    if any(k in text for k in ("sec ", "regulation", "regulatory", "ban", "lawsuit", "监管", "起诉")):
        return "regulatory"
    if any(k in text for k in ("binance", "coinbase", "okx", "bybit", "listing", "delist", "上线", "下架")):
        return "exchange"
    if any(k in text for k in ("liquidat", "清算", "爆仓")):
        return "liquidation"
    if any(k in text for k in ("etf", "blackrock", "grayscale", "approval", "etf")):
        return "breaking"
    if any(k in text for k in ("cpi", "fed", "fomc", "rate", "inflation")):
        return "macro"
    return "breaking"


def _news_importance(text: str) -> int:
    score = 2
    high = (
        "sec", "etf", "fed", "fomc", "cpi", "hack", "exploit", "bankrupt", "liquidat",
        "blackrock", "trump", "war", "制裁", "etf", "破产", "黑客", "攻击",
    )
    if any(k in text for k in high):
        score += 2
    if any(k in text for k in ("bitcoin", "btc", "比特币")):
        score += 1
    return min(score, 5)


def _news_btc_relevance(text: str) -> float:
    score = 0.3
    if any(k in text for k in ("bitcoin", "btc", "比特币")):
        score += 0.35
    if any(k in text for k in ("crypto", "ethereum", "eth", "加密")):
        score += 0.15
    if any(k in text for k in ("fed", "cpi", "etf", "sec", "macro")):
        score += 0.2
    return min(score, 1.0)


def _news_tags(text: str) -> list[str]:
    tags: list[str] = []
    for kw in ("btc", "bitcoin", "etf", "fed", "sec", "liquidation", "hack", "binance"):
        if kw in text:
            tags.append(kw)
    return tags or ["news"]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def _ms_to_iso(ms: Any) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc).isoformat()


def _event_id(prefix: str, title: str, ts: str) -> str:
    raw = f"{prefix}|{title}|{ts}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

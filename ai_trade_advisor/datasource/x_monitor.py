from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

import requests

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.bigevent.models import MarketEvent

# 影响 BTC 的 X 监控关键词（搜索 query）
DEFAULT_X_QUERY = (
    '(bitcoin OR BTC OR "BlackRock" OR ETF OR FOMC OR CPI OR SEC OR Binance OR '
    '"rate cut" OR liquidation OR hack OR Trump OR tariff) '
    "-is:retweet lang:en"
)

# 高权重账号（crypto / macro 权威来源）
TRUSTED_ACCOUNTS = frozenset({
    "cz_binance", "saylor", "elonmusk", "realDonaldTrump", "POTUS",
    "federalreserve", "SECGov", "BlackRock", "CoinDesk", "WuBlockchain",
    "lookonchain", "whale_alert", "tier10k", "tree_of_alpha",
})

BEARISH_KEYWORDS = (
    "hack", "exploit", "ban", "lawsuit", "crackdown", "sell", "dump", "crash",
    "liquidat", "bankrupt", "insolvent", "outflow", "tariff", "sanction",
    "攻击", "黑客", "禁止", "暴跌", "清算", "破产",
)
BULLISH_KEYWORDS = (
    "approval", "approve", "etf inflow", "buy", "accumul", "rate cut",
    "dovish", "pivot", "ath", "breakout", "inflow", "adopt",
    "批准", "流入", "降息", "突破",
)
BREAKING_KEYWORDS = (
    "breaking", "just in", "urgent", "alert", "confirmed", "report",
    "突发", "快讯", "确认",
)


def fetch_x_breaking(cfg: AdvisorConfig) -> list[MarketEvent]:
    """X (Twitter) 近期推文搜索，发现 BTC 相关突发事件。"""
    if not cfg.x_bearer_token:
        return _demo_x_events() if cfg.event_demo_mode else []

    query = cfg.x_search_query or DEFAULT_X_QUERY
    try:
        tweets = _search_recent(cfg.x_bearer_token, query, max_results=cfg.x_max_results)
    except Exception:
        return []

    events: list[MarketEvent] = []
    for tw in tweets:
        event = _tweet_to_event(tw)
        if event and event.btc_relevance >= cfg.event_min_btc_relevance:
            events.append(event)
    return events


def _search_recent(bearer: str, query: str, *, max_results: int) -> list[dict[str, Any]]:
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {bearer}"}
    params = {
        "query": query,
        "max_results": min(max(max_results, 10), 100),
        "tweet.fields": "created_at,public_metrics,author_id,lang",
        "expansions": "author_id",
        "user.fields": "username,verified,public_metrics",
    }
    resp = requests.get(url, headers=headers, params=params, timeout=25)
    resp.raise_for_status()
    data = resp.json()
    users = {u["id"]: u for u in (data.get("includes") or {}).get("users") or []}
    out: list[dict[str, Any]] = []
    for tw in data.get("data") or []:
        author = users.get(tw.get("author_id"), {})
        out.append({"tweet": tw, "author": author})
    return out


def _tweet_to_event(item: dict[str, Any]) -> MarketEvent | None:
    tw = item.get("tweet") or {}
    author = item.get("author") or {}
    text = str(tw.get("text") or "").strip()
    if len(text) < 20:
        return None

    username = str(author.get("username") or "unknown")
    verified = bool(author.get("verified"))
    created = str(tw.get("created_at") or datetime.now(timezone.utc).isoformat())
    tweet_id = str(tw.get("id") or "")
    url = f"https://x.com/{username}/status/{tweet_id}" if tweet_id else None
    lower = text.lower()

    importance = 2
    if username.lower() in {a.lower() for a in TRUSTED_ACCOUNTS}:
        importance += 2
    if verified:
        importance += 1
    if any(k in lower for k in BREAKING_KEYWORDS):
        importance += 1
    metrics = tw.get("public_metrics") or {}
    if int(metrics.get("retweet_count") or 0) > 500:
        importance += 1

    btc_rel = _tweet_btc_relevance(lower)
    category = _tweet_category(lower)

    followers = int((author.get("public_metrics") or {}).get("followers_count") or 0)
    if followers > 1_000_000:
        btc_rel = min(btc_rel + 0.1, 1.0)

    tags = ["x", username]
    if verified:
        tags.append("verified")
    for kw in ("etf", "sec", "fed", "hack", "liquidation", "binance"):
        if kw in lower:
            tags.append(kw)

    return MarketEvent(
        id=_event_id("x", tweet_id or text[:40], created),
        title=_truncate(text, 140),
        summary=text,
        category=category,
        source=f"x:@{username}",
        published_at=created,
        importance=min(importance, 5),
        btc_relevance=btc_rel,
        tags=tags,
        source_url=url,
        raw={"tweet": tw, "author": author},
    )


def _tweet_btc_relevance(text: str) -> float:
    score = 0.25
    if any(k in text for k in ("bitcoin", "btc", "$btc")):
        score += 0.4
    if any(k in text for k in ("crypto", "ethereum", "eth")):
        score += 0.1
    if any(k in text for k in ("fed", "fomc", "cpi", "etf", "sec", "rate")):
        score += 0.25
    if any(k in text for k in ("liquidat", "hack", "blackrock", "binance")):
        score += 0.15
    return min(score, 1.0)


def _tweet_category(text: str) -> str:
    if any(k in text for k in ("sec", "regulation", "lawsuit", "ban")):
        return "regulatory"
    if any(k in text for k in ("liquidat", "whale", "清算")):
        return "liquidation"
    if any(k in text for k in ("hack", "exploit", "attack")):
        return "breaking"
    if any(k in text for k in ("cpi", "fed", "fomc", "rate")):
        return "macro"
    return "breaking"


def _demo_x_events() -> list[MarketEvent]:
    """无 X API Key 时的演示数据，便于 UI 联调。"""
    now = datetime.now(timezone.utc).isoformat()
    samples = [
        ("Whale Alert: 5,000 BTC transferred from unknown wallet to Coinbase", "liquidation", 4, 0.9),
        ("BREAKING: Fed officials signal potential rate cut in upcoming meeting", "macro", 5, 0.85),
        ("SEC delays decision on spot Bitcoin ETF application", "regulatory", 4, 0.8),
    ]
    out: list[MarketEvent] = []
    for title, cat, imp, rel in samples:
        out.append(
            MarketEvent(
                id=_event_id("x:demo", title, now),
                title=title,
                summary=title,
                category=cat,  # type: ignore[arg-type]
                source="x:demo",
                published_at=now,
                importance=imp,
                btc_relevance=rel,
                tags=["x", "demo"],
                source_url=None,
            )
        )
    return out


def _truncate(text: str, n: int) -> str:
    text = re.sub(r"https?://\S+", "", text).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def _event_id(prefix: str, key: str, ts: str) -> str:
    return hashlib.sha256(f"{prefix}|{key}|{ts}".encode()).hexdigest()[:16]

from __future__ import annotations

import csv
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.paths import get_etf_root
from ai_trade_advisor.models import EtfFlowDay, EtfTickerFlow

FARSIDE_BTC_ALL_DATA_URL = "https://farside.co.uk/bitcoin-etf-flow-all-data/"
FARSIDE_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_DATE_RE = re.compile(r"^\d{1,2} \w{3} \d{4}$")
_SKIP_COLUMNS = frozenset({"Date", "Total", "Fee", "BTC"})
def _etfdata_dir(cfg: AdvisorConfig) -> Path:
    if cfg.etfdata_dir is not None:
        return cfg.etfdata_dir
    return get_etf_root()


def fetch_farside_btc_daily(*, days_back: int = 120, timeout: float = 30.0) -> list[EtfFlowDay]:
    """爬取 Farside Investors BTC Spot ETF 日度净流入（百万美元 → USD）。"""
    html = _fetch_farside_html(timeout=timeout)
    days = parse_farside_btc_table(html)
    if days_back > 0:
        cutoff = (datetime.now(UTC).date() - timedelta(days=days_back - 1)).isoformat()
        days = [d for d in days if d.date >= cutoff]
    return days


def _fetch_farside_html(*, timeout: float = 30.0) -> str:
    resp = requests.get(
        FARSIDE_BTC_ALL_DATA_URL,
        headers={"User-Agent": FARSIDE_USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.text


def parse_farside_btc_table(html: str) -> list[EtfFlowDay]:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 2:
        raise ValueError("Farside 页面结构变化：table 数量不足")

    table = tables[1]
    rows = table.find_all("tr")
    if not rows:
        raise ValueError("Farside 页面结构变化：主表无行")

    header = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    if "Date" not in header or "Total" not in header:
        raise ValueError(f"Farside 表头异常，缺少 Date/Total: {header[:8]}")

    date_idx = header.index("Date")
    total_idx = header.index("Total")
    ticker_cols = [
        (i, col)
        for i, col in enumerate(header)
        if col not in _SKIP_COLUMNS and i not in (date_idx, total_idx)
    ]

    days: list[EtfFlowDay] = []
    seen_dates: set[str] = set()
    for row in rows[1:]:
        cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
        if len(cells) <= max(date_idx, total_idx):
            continue
        raw_date = cells[date_idx].strip()
        if not _DATE_RE.match(raw_date) or raw_date in seen_dates:
            continue
        seen_dates.add(raw_date)

        total = _parse_farside_usd(cells[total_idx])
        if total is None:
            continue

        tickers: list[EtfTickerFlow] = []
        for col_idx, ticker in ticker_cols:
            if col_idx >= len(cells):
                continue
            flow = _parse_farside_usd(cells[col_idx])
            if flow is not None:
                tickers.append(EtfTickerFlow(ticker=ticker, flow_usd=flow))
        tickers.sort(key=lambda t: abs(t.flow_usd), reverse=True)

        days.append(
            EtfFlowDay(
                date=_farside_date_to_iso(raw_date),
                flow_usd=total,
                price_usd=None,
                tickers=tickers,
            )
        )

    days.sort(key=lambda d: d.date)
    return days


def save_farside_btc_csv(days: list[EtfFlowDay], cfg: AdvisorConfig) -> tuple[Path, Path]:
    """将爬取结果写入 data/ETF/Btc/ 本地 CSV。"""
    base = _etfdata_dir(cfg) / "Btc"
    base.mkdir(parents=True, exist_ok=True)
    daily_path = base / "btc_etf_flow_daily.csv"
    tickers_path = base / "btc_etf_flow_tickers.csv"

    with open(daily_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "timestamp_ms", "flow_usd", "price_usd"])
        for d in days:
            ts_ms = int(datetime.strptime(d.date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() * 1000)
            w.writerow([d.date, ts_ms, d.flow_usd, d.price_usd if d.price_usd is not None else ""])

    with open(tickers_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "ticker", "flow_usd"])
        for d in days:
            for t in d.tickers:
                w.writerow([d.date, t.ticker, t.flow_usd])

    return daily_path, tickers_path


def _farside_date_to_iso(raw: str) -> str:
    return datetime.strptime(raw, "%d %b %Y").date().isoformat()


def _parse_farside_usd(raw: str) -> float | None:
    text = raw.strip().replace(",", "")
    if not text or text == "-":
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    try:
        value = float(text) * 1_000_000
    except ValueError:
        return None
    return -value if negative else value

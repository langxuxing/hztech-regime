from __future__ import annotations

import csv
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.farside_etf import fetch_farside_btc_daily
from ai_trade_advisor.datasource.fund_flow import _coinglass_get
from ai_trade_advisor.datasource.paths import get_etf_root
from ai_trade_advisor.models import EtfFlowDay, EtfFlowSnapshot, EtfFlowWeek, EtfTickerFlow

ETF_PATHS = {
    "BTC": "/api/etf/bitcoin/flow-history",
    "ETH": "/api/etf/ethereum/flow-history",
}
_ETF_LOCAL_DIRS = {"BTC": "Btc", "ETH": "Eth"}
_WEEKLY_LOOKBACK_DAYS = 90
_WEEKLY_PERIODS = 13


def _etfdata_dir(cfg: AdvisorConfig) -> Path:
    if cfg.etfdata_dir is not None:
        return cfg.etfdata_dir
    return get_etf_root()


def fetch_etf_flows(cfg: AdvisorConfig, asset: str) -> EtfFlowSnapshot | None:
    """Spot ETF 日度净流入/流出；BTC 优先本地 CSV / Farside 爬虫，ETH 走 CoinGlass。"""
    asset = asset.upper()
    local = load_local_etf_flows(cfg, asset)
    if local is not None:
        return local
    if asset == "BTC":
        scraped = _fetch_btc_farside(cfg)
        if scraped is not None:
            return scraped
    return _fetch_etf_flows_api(cfg, asset)


def _fetch_btc_farside(cfg: AdvisorConfig) -> EtfFlowSnapshot | None:
    try:
        days = fetch_farside_btc_daily(days_back=max(_WEEKLY_LOOKBACK_DAYS, 30))
    except Exception:
        return None
    if not days:
        return None
    return _snapshot_from_history("BTC", days, source="farside:scrape")


def load_local_etf_flows(cfg: AdvisorConfig, asset: str) -> EtfFlowSnapshot | None:
    """读取本地日度 CSV（Farside 或 CoinGlass 导出）。"""
    asset = asset.upper()
    sub = _ETF_LOCAL_DIRS.get(asset, asset)
    prefix = asset.lower()
    base = _etfdata_dir(cfg) / sub
    daily_path = base / f"{prefix}_etf_flow_daily.csv"
    if not daily_path.is_file():
        return None
    history = _read_daily_csv(daily_path, tickers_path=base / f"{prefix}_etf_flow_tickers.csv")
    if not history:
        return None
    source = "local:farside_csv" if asset == "BTC" else "local:etf_flow_csv"
    return _snapshot_from_history(asset, history, source=source)


def _fetch_etf_flows_api(cfg: AdvisorConfig, asset: str) -> EtfFlowSnapshot | None:
    path = ETF_PATHS.get(asset.upper())
    if not path or not cfg.coinglass_api_key:
        return None
    try:
        rows = _coinglass_get(cfg, path, {})
    except Exception:
        return None
    if not isinstance(rows, list) or not rows:
        return None

    history: list[EtfFlowDay] = []
    for row in rows[-max(_WEEKLY_LOOKBACK_DAYS, 30) :]:
        day = parse_etf_day_row(row)
        if day:
            history.append(day)
    if not history:
        return None
    return _snapshot_from_history(asset.upper(), history, source="coinglass:etf_flow")


def aggregate_weekly(days: list[EtfFlowDay], *, weeks: int = _WEEKLY_PERIODS) -> list[EtfFlowWeek]:
    """按 ISO 周聚合日度净流入，返回最近 N 周。"""
    buckets: dict[tuple[int, int], list[EtfFlowDay]] = defaultdict(list)
    for day in days:
        dt = date.fromisoformat(day.date)
        iso = dt.isocalendar()
        buckets[(iso.year, iso.week)].append(day)

    weekly: list[EtfFlowWeek] = []
    for year, week in sorted(buckets):
        items = sorted(buckets[(year, week)], key=lambda d: d.date)
        monday = date.fromisoformat(items[0].date) - timedelta(days=date.fromisoformat(items[0].date).weekday())
        sunday = monday + timedelta(days=6)
        weekly.append(
            EtfFlowWeek(
                week_start=monday.isoformat(),
                week_end=sunday.isoformat(),
                flow_usd=sum(d.flow_usd for d in items),
                label=f"{year}-W{week:02d}",
                days_count=len(items),
            )
        )
    return weekly[-weeks:]


def _snapshot_from_history(asset: str, history: list[EtfFlowDay], *, source: str) -> EtfFlowSnapshot:
    latest = history[-1]
    total_7d = sum(d.flow_usd for d in history[-7:])
    total_30d = sum(d.flow_usd for d in history[-30:])
    weekly_source = [d for d in history if d.date >= _weekly_cutoff_date()]
    weekly_history = aggregate_weekly(weekly_source)
    total_13w = sum(w.flow_usd for w in weekly_history) if weekly_history else None
    return EtfFlowSnapshot(
        asset=asset,
        latest=latest,
        history=history[-7:],
        weekly_history=weekly_history,
        total_7d_usd=total_7d,
        total_30d_usd=total_30d,
        total_13w_usd=total_13w,
        interpretation=_interpret_etf(latest.flow_usd, total_7d, weekly_history),
        source=source,
    )


def _weekly_cutoff_date() -> str:
    return (datetime.now(UTC).date() - timedelta(days=_WEEKLY_LOOKBACK_DAYS - 1)).isoformat()


def _read_daily_csv(daily_path: Path, *, tickers_path: Path | None = None) -> list[EtfFlowDay]:
    tickers_by_date: dict[str, list[EtfTickerFlow]] = {}
    if tickers_path and tickers_path.is_file():
        with open(tickers_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                date_val = (row.get("date") or "").strip()
                ticker = (row.get("ticker") or "").strip()
                flow = _float(row.get("flow_usd"))
                if date_val and ticker and flow is not None:
                    tickers_by_date.setdefault(date_val, []).append(EtfTickerFlow(ticker=ticker, flow_usd=flow))
        for items in tickers_by_date.values():
            items.sort(key=lambda t: abs(t.flow_usd), reverse=True)

    days: list[EtfFlowDay] = []
    with open(daily_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            date_val = (row.get("date") or "").strip()
            flow = _float(row.get("flow_usd"))
            if not date_val or flow is None:
                continue
            tickers = tickers_by_date.get(date_val, [])[:8]
            days.append(
                EtfFlowDay(
                    date=date_val,
                    flow_usd=flow,
                    price_usd=_float(row.get("price_usd")),
                    tickers=tickers,
                )
            )
    days.sort(key=lambda d: d.date)
    return days


def parse_etf_day_row(row: dict[str, Any], *, max_tickers: int | None = 8) -> EtfFlowDay | None:
    ts = row.get("timestamp")
    flow = _float(row.get("flow_usd"))
    if flow is None:
        return None
    date_val = _ts_to_date(ts)
    tickers: list[EtfTickerFlow] = []
    for item in row.get("etf_flows") or []:
        ticker = str(item.get("etf_ticker") or item.get("ticker") or "").strip()
        t_flow = _float(item.get("flow_usd"))
        if ticker and t_flow is not None:
            tickers.append(EtfTickerFlow(ticker=ticker, flow_usd=t_flow))
    tickers.sort(key=lambda t: abs(t.flow_usd), reverse=True)
    if max_tickers is not None:
        tickers = tickers[:max_tickers]
    return EtfFlowDay(
        date=date_val,
        flow_usd=flow,
        price_usd=_float(row.get("price_usd")),
        tickers=tickers,
    )


def _interpret_etf(latest_usd: float, total_7d: float, weekly: list[EtfFlowWeek]) -> str:
    parts: list[str] = []
    if latest_usd >= 100_000_000:
        parts.append(f"最新日净流入 {_fmt_usd(latest_usd)}，机构买盘强劲")
    elif latest_usd <= -100_000_000:
        parts.append(f"最新日净流出 {_fmt_usd(abs(latest_usd))}，机构获利/减仓")
    else:
        parts.append(f"最新日净流 {_fmt_usd(latest_usd)}")

    if total_7d >= 500_000_000:
        parts.append("7 日累计大幅净流入")
    elif total_7d <= -500_000_000:
        parts.append("7 日累计大幅净流出")
    else:
        parts.append(f"7 日累计 {_fmt_usd(total_7d)}")

    if weekly:
        total_13w = sum(w.flow_usd for w in weekly)
        inflow_weeks = sum(1 for w in weekly if w.flow_usd > 0)
        parts.append(f"近 {len(weekly)} 周累计 {_fmt_usd(total_13w)}（{inflow_weeks} 周净流入）")
    return "；".join(parts)


def _fmt_usd(v: float) -> str:
    sign = "+" if v >= 0 else "-"
    av = abs(v)
    if av >= 1e9:
        return f"{sign}${av / 1e9:.2f}B"
    if av >= 1e6:
        return f"{sign}${av / 1e6:.0f}M"
    return f"{sign}${av:,.0f}"


def _ts_to_date(ts: Any) -> str:
    if ts is None:
        return datetime.now(UTC).date().isoformat()
    try:
        ms = int(ts)
        if ms > 1e12:
            ms //= 1000
        return datetime.fromtimestamp(ms, tz=UTC).date().isoformat()
    except (TypeError, ValueError):
        return str(ts)[:10]


def _float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

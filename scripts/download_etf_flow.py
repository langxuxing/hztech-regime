#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 CoinGlass 下载 Spot ETF 日度净流入/流出，保存为本地 CSV。

数据源（需 COINGLASS_API_KEY，Hobbyist+）：
  BTC: GET /api/etf/bitcoin/flow-history
  ETH: GET /api/etf/ethereum/flow-history

输出（默认 data/ETF/{Btc,Eth}/）：
  {asset}_etf_flow_daily.csv   — date,timestamp_ms,flow_usd,price_usd
  {asset}_etf_flow_tickers.csv — date,ticker,flow_usd
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.etf_flow import ETF_PATHS, parse_etf_day_row
from ai_trade_advisor.datasource.fund_flow import _coinglass_get
from ai_trade_advisor.datasource.paths import get_etf_root
from ai_trade_advisor.models import EtfFlowDay

logger = logging.getLogger(__name__)

DEFAULT_OUT = get_etf_root()
ASSET_DIRS = {"BTC": "Btc", "ETH": "Eth"}


def fetch_etf_history(cfg: AdvisorConfig, asset: str) -> list[dict]:
    path = ETF_PATHS.get(asset.upper())
    if not path:
        raise ValueError(f"不支持的资产: {asset}")
    rows = _coinglass_get(cfg, path, {})
    if not isinstance(rows, list):
        raise ValueError(f"CoinGlass 返回异常: {asset}")
    return rows


def filter_last_days(days: list[EtfFlowDay], *, days_back: int) -> list[EtfFlowDay]:
    if days_back <= 0:
        return days
    cutoff = (datetime.now(UTC).date() - timedelta(days=days_back - 1)).isoformat()
    return [d for d in days if d.date >= cutoff]


def save_asset_csv(
    asset: str,
    days: list[EtfFlowDay],
    out_dir: Path,
    *,
    ts_by_date: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    sub = ASSET_DIRS.get(asset.upper(), asset.upper())
    base = out_dir / sub
    base.mkdir(parents=True, exist_ok=True)
    prefix = asset.lower()
    daily_path = base / f"{prefix}_etf_flow_daily.csv"
    tickers_path = base / f"{prefix}_etf_flow_tickers.csv"

    with open(daily_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "timestamp_ms", "flow_usd", "price_usd"])
        for d in days:
            ts_raw = (ts_by_date or {}).get(d.date)
            if ts_raw is not None:
                ts_ms = int(ts_raw)
            else:
                ts_ms = int(datetime.strptime(d.date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() * 1000)
            w.writerow([d.date, ts_ms, d.flow_usd, d.price_usd if d.price_usd is not None else ""])

    with open(tickers_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "ticker", "flow_usd"])
        for d in days:
            for t in d.tickers:
                w.writerow([d.date, t.ticker, t.flow_usd])

    return daily_path, tickers_path


def download_etf_flows(
    cfg: AdvisorConfig,
    *,
    assets: list[str],
    days_back: int = 365,
    out_dir: Path | None = None,
) -> dict[str, tuple[Path, Path]]:
    if not cfg.coinglass_api_key:
        raise SystemExit(
            "未配置 COINGLASS_API_KEY。请在 .env 中设置 CoinGlass API Key（Hobbyist+ 套餐）。"
        )
    out = out_dir or DEFAULT_OUT
    written: dict[str, tuple[Path, Path]] = {}
    for asset in assets:
        asset = asset.upper()
        logger.info("拉取 %s Spot ETF 历史...", asset)
        raw = fetch_etf_history(cfg, asset)
        parsed: list[tuple[EtfFlowDay, Any]] = []
        for row in raw:
            day = parse_etf_day_row(row, max_tickers=None)
            if day:
                ts = row.get("timestamp")
                parsed.append((day, ts))
        parsed.sort(key=lambda x: x[0].date)
        selected = filter_last_days([d for d, _ in parsed], days_back=days_back)
        if not selected:
            logger.warning("%s 无可用数据（可能 API 权限不足或日期过滤后为空）", asset)
            continue
        ts_by_date = {d.date: ts for d, ts in parsed}
        daily_path, tickers_path = save_asset_csv(asset, selected, out, ts_by_date=ts_by_date)
        total_flow = sum(d.flow_usd for d in selected)
        logger.info(
            "%s: %d 天 (%s ~ %s)，累计净流 $%.2fM → %s",
            asset,
            len(selected),
            selected[0].date,
            selected[-1].date,
            total_flow / 1e6,
            daily_path,
        )
        written[asset] = (daily_path, tickers_path)
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    p = argparse.ArgumentParser(description="下载 BTC/ETH Spot ETF 日度净流入 CSV（CoinGlass）")
    p.add_argument("--assets", default="BTC,ETH", help="逗号分隔，默认 BTC,ETH")
    p.add_argument("--days", type=int, default=365, help="回溯天数，默认 365（约 1 年）")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT), help=f"输出目录，默认 {DEFAULT_OUT}")
    p.add_argument("--api-key", default="", help="可选，覆盖 .env 中的 COINGLASS_API_KEY")
    args = p.parse_args()

    cfg = AdvisorConfig.from_env()
    if args.api_key.strip():
        cfg.coinglass_api_key = args.api_key.strip()
    elif os.getenv("COINGLASS_API_KEY", "").strip():
        cfg.coinglass_api_key = os.getenv("COINGLASS_API_KEY", "").strip()

    assets = [a.strip().upper() for a in args.assets.split(",") if a.strip()]
    paths = download_etf_flows(cfg, assets=assets, days_back=args.days, out_dir=Path(args.out_dir))
    print(f"Done, assets: {len(paths)}")
    for asset, (daily, tickers) in paths.items():
        print(f"  {asset}: {daily}")
        print(f"         {tickers}")


if __name__ == "__main__":
    main()

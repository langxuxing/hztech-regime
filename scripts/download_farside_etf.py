#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 Farside Investors 爬取 BTC Spot ETF 日度净流入/流出，保存为本地 CSV。

数据源（免费，无需 API Key）：
  https://farside.co.uk/bitcoin-etf-flow-all-data/

输出（默认 data/ETF/Btc/）：
  btc_etf_flow_daily.csv   — date,timestamp_ms,flow_usd,price_usd
  btc_etf_flow_tickers.csv — date,ticker,flow_usd
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.farside_etf import fetch_farside_btc_daily, save_farside_btc_csv
from ai_trade_advisor.datasource.paths import get_etf_root

logger = logging.getLogger(__name__)
DEFAULT_OUT = get_etf_root()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    p = argparse.ArgumentParser(description="爬取 Farside BTC Spot ETF 日度净流入 CSV")
    p.add_argument("--days", type=int, default=365, help="回溯天数，默认 365")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT), help=f"输出根目录，默认 {DEFAULT_OUT}")
    args = p.parse_args()

    cfg = AdvisorConfig.from_env()
    cfg.etfdata_dir = Path(args.out_dir)

    logger.info("爬取 Farside BTC ETF 历史（近 %d 天）...", args.days)
    days = fetch_farside_btc_daily(days_back=args.days)
    if not days:
        raise SystemExit("Farside 爬取失败或无数据")

    daily_path, tickers_path = save_farside_btc_csv(days, cfg)
    total_flow = sum(d.flow_usd for d in days)
    logger.info(
        "%d 天 (%s ~ %s)，累计净流 $%.2fM",
        len(days),
        days[0].date,
        days[-1].date,
        total_flow / 1e6,
    )
    print(f"Done: {daily_path}")
    print(f"      {tickers_path}")


if __name__ == "__main__":
    main()

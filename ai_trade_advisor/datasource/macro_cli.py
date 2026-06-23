#!/usr/bin/env python3
"""宏观数据爬取 CLI：M2 / ISM / PPI / 基准利率 / CPI / 非农。"""

from __future__ import annotations

import argparse
import sys

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.macro_fetch import fetch_and_save_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="爬取宏观指标 (M2/制造业活动/PPI/基准利率/CPI/非农) 并写入本地 data/macro/"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="单次 HTTP 超时秒数（默认 30）",
    )
    args = parser.parse_args(argv)

    cfg = AdvisorConfig.from_env()
    try:
        results = fetch_and_save_all(cfg, timeout=args.timeout)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    root = cfg.data_dir / "macro"
    print(f"数据目录: {root}")
    for r in results:
        print(
            f"  [{r.indicator}] {r.latest_date} = {r.latest_value}  "
            f"({r.rows} 行) → {r.path.name}"
        )
    print(f"摘要: {root / 'summary.csv'}")
    print(f"快照: {root / 'latest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

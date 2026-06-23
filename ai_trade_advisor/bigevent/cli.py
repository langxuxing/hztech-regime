#!/usr/bin/env python3
"""事件分析 CLI。"""

from __future__ import annotations

import argparse
import json
import sys

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.bigevent.engine import run_event_analysis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BTC 事件分析引擎")
    parser.add_argument("-o", "--output", help="输出 JSON 文件路径")
    parser.add_argument("--skip-x", action="store_true", help="跳过 X 监控")
    parser.add_argument("--skip-exchange", action="store_true", help="跳过交易所公告")
    parser.add_argument("--skip-calendar", action="store_true", help="跳过 CoinGlass 日历")
    parser.add_argument("--pretty", action="store_true", help="格式化 JSON 输出")
    args = parser.parse_args(argv)

    cfg = AdvisorConfig.from_env()
    snap = run_event_analysis(
        cfg,
        skip_x=args.skip_x,
        skip_exchange=args.skip_exchange,
        skip_calendar=args.skip_calendar,
    )
    payload = snap.to_dict()
    text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已写入 {args.output}")
    else:
        print(text)

    summary = payload.get("summary") or {}
    print(
        f"\n扫描完成: 日历 {summary.get('total_calendar', 0)} | "
        f"突发 {summary.get('total_breaking', 0)} | "
        f"高风险 {summary.get('high_impact_count', 0)} | "
        f"整体风险 {summary.get('overall_risk', '?')}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

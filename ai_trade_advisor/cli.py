#!/usr/bin/env python3
"""AI 交易建议系统 CLI。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.pipeline import run_advisor
from ai_trade_advisor.serialize import dashboard_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI 交易建议系统（结构化数据 → LLM/规则引擎）")
    parser.add_argument("--exchange", default="", help="okx | binance")
    parser.add_argument("--symbol", default="", help="如 BTC/USDT:USDT")
    parser.add_argument("--bar-minutes", type=int, default=0, help="K 线周期，默认 30")
    parser.add_argument("--context-only", action="store_true", help="仅输出结构化特征文本")
    parser.add_argument("--skip-orderbook", action="store_true", help="跳过订单簿（离线调试）")
    parser.add_argument("--skip-capital-flows", action="store_true", help="跳过 BTC/ETH 资金流与链上数据")
    parser.add_argument("--use-local-pepe", action="store_true", help="使用本地 PEPE 1m 数据")
    parser.add_argument("--output", "-o", default="", help="JSON 输出路径")
    args = parser.parse_args(argv)

    cfg = AdvisorConfig.from_env()
    if args.exchange:
        cfg.exchange = args.exchange
    if args.symbol:
        cfg.symbol = args.symbol
    if args.bar_minutes:
        cfg.bar_minutes = args.bar_minutes
    if args.use_local_pepe:
        cfg.use_local_pepe = True

    try:
        ctx, advice, structured, board = run_advisor(
            cfg,
            skip_orderbook=args.skip_orderbook,
            skip_capital_flows=args.skip_capital_flows,
        )
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    if args.context_only:
        print(structured)
        return 0

    result = dashboard_payload(
        ctx,
        advice,
        mode="rule_based" if advice.rule_based else "llm",
        board=board,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"已写入 {args.output}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

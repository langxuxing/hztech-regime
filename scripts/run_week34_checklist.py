#!/usr/bin/env python3
"""第 3–4 周验收清单：数据管道 + 趋势监控 + 反馈闭环。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.paths import get_data_root
from ai_trade_advisor.ops.week34_checklist import run_week34_checklist
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(description="第 3–4 周生产验收清单")
    parser.add_argument("-o", "--output", type=Path, help="JSON 报告输出路径")
    parser.add_argument("--week", type=int, choices=[3, 4], help="仅检查指定周")
    args = parser.parse_args()

    cfg = AdvisorConfig.from_env()
    report = run_week34_checklist(cfg)
    data = report.to_dict()

    if args.week == 3:
        passed = report.week3_passed
        data["checks"] = [c for c in data["checks"] if c["week"] == 3]
    elif args.week == 4:
        passed = report.week4_passed
        data["checks"] = [c for c in data["checks"] if c["week"] == 4]
    else:
        passed = report.all_passed

    text = json.dumps(data, ensure_ascii=False, indent=2)
    print(text)

    out = args.output or (get_data_root() / "exports" / "reviews" / "week34_checklist_latest.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"\n报告: {out}", file=sys.stderr)

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

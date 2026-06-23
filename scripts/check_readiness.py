#!/usr/bin/env python3
"""打印生产就绪度报告（JSON）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.readiness import check_readiness


def main() -> int:
    report = check_readiness(AdvisorConfig.from_env())
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.tier == "production" else 1


if __name__ == "__main__":
    raise SystemExit(main())

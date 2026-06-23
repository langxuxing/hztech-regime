#!/usr/bin/env python3
"""趋势判断健康检查 CLI。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.paths import get_data_root
from ai_trade_advisor.regime.trend_health import run_trend_health_check
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    report = run_trend_health_check(AdvisorConfig.from_env())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    out = get_data_root() / "exports" / "reviews" / "trend_health_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["status"] == "critical":
        return 1
    if report["status"] == "degraded":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

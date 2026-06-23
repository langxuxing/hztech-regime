#!/usr/bin/env python3
"""校准器基线运行：无人工样本时写入默认参数报告。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.paths import get_data_root
from ai_trade_advisor.regime.feedback.calibrator import run_calibration
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    cfg = AdvisorConfig.from_env()
    report = run_calibration(cfg, symbol=cfg.symbol)
    report["baseline_run"] = True
    report["generated_at"] = datetime.now(timezone.utc).isoformat()

    out_dir = get_data_root() / "exports" / "reviews"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"calibrator_baseline_{stamp}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"已写入 {out_path}", file=sys.stderr)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

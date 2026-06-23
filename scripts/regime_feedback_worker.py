#!/usr/bin/env python3
"""Regime 反馈闭环后台任务：延迟打分 + rollup + 校准。"""

from __future__ import annotations

import argparse
import time

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.regime.feedback.calibrator import run_calibration
from ai_trade_advisor.regime.feedback.worker import run_forward_scoring_batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regime feedback worker")
    parser.add_argument("--once", action="store_true", help="运行一次后退出")
    parser.add_argument("--forward-only", action="store_true")
    parser.add_argument("--calibrate-only", action="store_true")
    args = parser.parse_args(argv)

    cfg = AdvisorConfig.from_env()

    def _tick() -> None:
        if not args.calibrate_only:
            result = run_forward_scoring_batch(cfg)
            print(f"[forward] processed={result['processed']} errors={result.get('errors')}")
        if not args.forward_only:
            cal = run_calibration(cfg)
            print(f"[calibrate] ok={cal.get('ok')} activated={cal.get('activated')}")

    if args.once:
        _tick()
        return 0

    interval_h = max(cfg.regime_calibration_interval_hours, 1)
    while True:
        _tick()
        time.sleep(interval_h * 3600)


if __name__ == "__main__":
    raise SystemExit(main())

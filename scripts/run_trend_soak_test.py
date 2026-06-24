#!/usr/bin/env python3
"""趋势判断 soak 测试：定时采样 /api/trend-health 等价逻辑并汇总。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.paths import get_data_root
from ai_trade_advisor.regime.trend_soak import collect_soak_sample, summarize_soak_samples
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def run_soak(
    cfg: AdvisorConfig,
    *,
    hours: float,
    interval_sec: int,
    max_samples: int | None = None,
) -> dict:
    started = datetime.now(timezone.utc)
    deadline = started.timestamp() + hours * 3600
    samples: list[dict] = []

    while True:
        samples.append(collect_soak_sample(cfg))
        if max_samples is not None and len(samples) >= max_samples:
            break
        if datetime.now(timezone.utc).timestamp() >= deadline:
            break
        time.sleep(max(0, interval_sec))

    summary = summarize_soak_samples(samples)
    return {
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "hours": hours,
            "interval_sec": interval_sec,
            "max_samples": max_samples,
            "symbol": cfg.symbol,
        },
        "samples": samples,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="趋势判断 soak 测试")
    parser.add_argument("--hours", type=float, default=48.0, help="运行时长（小时），默认 48")
    parser.add_argument("--interval-sec", type=int, default=300, help="采样间隔（秒），默认 300")
    parser.add_argument("--samples", type=int, help="固定采样次数（覆盖 hours）")
    parser.add_argument("-o", "--output", type=Path, help="JSON 报告输出路径")
    args = parser.parse_args()

    cfg = AdvisorConfig.from_env()
    report = run_soak(
        cfg,
        hours=args.hours,
        interval_sec=args.interval_sec,
        max_samples=args.samples,
    )

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)

    out = args.output or (
        get_data_root() / "exports" / "reviews" / "trend_soak_latest.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"\n报告已写入: {out}")

    status = report["summary"]["status"]
    if status == "critical":
        return 1
    if status == "degraded":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

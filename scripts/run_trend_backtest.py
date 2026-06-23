#!/usr/bin/env python3
"""趋势判断历史回测：walk-forward + 趋势质量指标 + JSON 报告。"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.backtest.regime_backtest import run_regime_backtest
from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.paths import get_data_root
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

REPORT_DIR = get_data_root() / "exports" / "reviews"


def _trend_metrics(timeline: list[dict]) -> dict:
    if not timeline:
        return {}

    trends = [str(t.get("raw_trend") or "range") for t in timeline]
    techs = [str(t.get("tech_trend") or t.get("raw_trend") or "range") for t in timeline]

    # trend duration
    durations: dict[str, list[int]] = {}
    current = trends[0]
    length = 1
    for t in trends[1:]:
        if t == current:
            length += 1
        else:
            durations.setdefault(current, []).append(length)
            current = t
            length = 1
    durations.setdefault(current, []).append(length)

    downgrade_count = sum(1 for tech, fused in zip(techs, trends) if tech == "uptrend" and fused == "range")
    upgrade_count = sum(1 for tech, fused in zip(techs, trends) if tech == "range" and fused in ("uptrend", "downtrend"))

    fake_wash = [t for t in timeline if t.get("regime_id") == "fake_breakout_wash"]
    fake_reversals = 0
    for i, row in enumerate(timeline):
        if row.get("regime_id") != "fake_breakout_wash":
            continue
        if i + 4 < len(timeline):
            future = timeline[i + 4]
            if float(future.get("close", 0)) < float(row.get("close", 0)):
                fake_reversals += 1

    return {
        "trend_distribution": dict(Counter(trends)),
        "avg_trend_duration_bars": {
            k: round(sum(v) / len(v), 2) for k, v in durations.items() if v
        },
        "tech_to_range_downgrades": downgrade_count,
        "range_to_trend_upgrades": upgrade_count,
        "fake_breakout_wash_count": len(fake_wash),
        "fake_breakout_reversal_within_4bars": fake_reversals,
        "fake_breakout_reversal_rate": round(fake_reversals / max(len(fake_wash), 1), 4),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="BTC 趋势判断 walk-forward 回测")
    parser.add_argument("--bars", type=int, default=720)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--output", "-o", default="")
    args = parser.parse_args(argv)

    cfg = AdvisorConfig.from_env()
    cfg.use_taker_cvd = True

    try:
        result = run_regime_backtest(
            cfg,
            bars=args.bars,
            warmup=args.warmup,
            store_timeline=True,
        )
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    trend_stats = _trend_metrics(result.timeline)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "type": "trend_backtest",
        "bars_evaluated": result.bars_evaluated,
        "warmup_bars": result.warmup_bars,
        "cvd_source": result.cvd_source,
        "regime_counts": result.regime_counts,
        "forward_returns": result.forward_returns,
        "trend_metrics": trend_stats,
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)

    out = args.output
    if not out:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = str(REPORT_DIR / f"trend_backtest_{stamp}.json")
    Path(out).write_text(text, encoding="utf-8")
    print(f"已写入 {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

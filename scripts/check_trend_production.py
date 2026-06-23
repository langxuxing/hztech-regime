#!/usr/bin/env python3
"""生产门禁：就绪度 + 趋势健康 + 人工反馈样本量。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.regime.feedback.stats import RECOMMENDATION_MIN_JUDGMENTS, build_feedback_stats
from ai_trade_advisor.regime.judgment_store import HumanJudgmentStore
from ai_trade_advisor.regime.trend_health import run_trend_health_check
from ai_trade_advisor.readiness import check_readiness
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def run_gate(
    cfg: AdvisorConfig,
    *,
    min_judgments: int = RECOMMENDATION_MIN_JUDGMENTS,
    require_production: bool = False,
) -> dict:
    readiness = check_readiness(cfg)
    health = run_trend_health_check(cfg)
    feedback = build_feedback_stats(
        symbol=cfg.symbol,
        cfg=cfg,
        judgment_store=HumanJudgmentStore(),
        min_judgments=min_judgments,
    )

    blockers: list[str] = []
    warnings: list[str] = []

    if health.get("status") == "critical":
        blockers.append("趋势健康 critical")
    elif health.get("status") == "degraded":
        warnings.append("趋势健康 degraded")

    if require_production and readiness.tier != "production":
        blockers.append(f"就绪度 {readiness.tier}，需要 production")

    if feedback["judgment_count"] < min_judgments:
        warnings.append(
            f"人工判断样本 {feedback['judgment_count']}/{min_judgments}"
        )

    if not feedback["recommendation_ready"] and cfg.regime_use_recommendation:
        warnings.append("REGIME_USE_RECOMMENDATION 已开但样本未就绪")

    passed = len(blockers) == 0
    return {
        "passed": passed,
        "readiness_tier": readiness.tier,
        "trend_health_status": health.get("status"),
        "feedback": feedback,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="趋势判断生产门禁")
    parser.add_argument(
        "--min-judgments",
        type=int,
        default=RECOMMENDATION_MIN_JUDGMENTS,
        help="推荐模型最低人工样本数",
    )
    parser.add_argument(
        "--require-production",
        action="store_true",
        help="要求 readiness tier = production",
    )
    parser.add_argument("-o", "--output", type=Path, help="写入 JSON 报告路径")
    args = parser.parse_args()

    cfg = AdvisorConfig.from_env()
    report = run_gate(
        cfg,
        min_judgments=args.min_judgments,
        require_production=args.require_production,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")

    if not report["passed"]:
        return 1
    if report["warnings"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

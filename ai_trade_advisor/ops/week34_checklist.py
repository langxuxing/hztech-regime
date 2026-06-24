"""第 3–4 周生产验收清单（数据管道 + 趋势监控 + 反馈闭环）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.capabilities import assess_data_capabilities
from ai_trade_advisor.datasource.ohlcv import load_local_btc_1m_csvs
from ai_trade_advisor.datasource.scheduler_meta import SchedulerMetaStore
from ai_trade_advisor.regime.feedback.stats import RECOMMENDATION_MIN_JUDGMENTS, build_feedback_stats
from ai_trade_advisor.regime.trend_health import run_trend_health_check
from ai_trade_advisor.readiness import check_readiness
from ai_trade_advisor.snapshot.store import SnapshotStore


@dataclass
class CheckItem:
    week: int
    category: str
    name: str
    passed: bool
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class Week34Report:
    generated_at: str
    week3_passed: bool
    week4_passed: bool
    all_passed: bool
    checks: list[CheckItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        w3 = [c for c in self.checks if c.week == 3]
        w4 = [c for c in self.checks if c.week == 4]
        return {
            "generated_at": self.generated_at,
            "week3": {
                "passed": self.week3_passed,
                "total": len(w3),
                "ok": sum(1 for c in w3 if c.passed),
            },
            "week4": {
                "passed": self.week4_passed,
                "total": len(w4),
                "ok": sum(1 for c in w4 if c.passed),
            },
            "all_passed": self.all_passed,
            "checks": [asdict(c) for c in self.checks],
        }


def run_week34_checklist(cfg: AdvisorConfig | None = None) -> Week34Report:
    cfg = cfg or AdvisorConfig.from_env()
    report = Week34Report(
        generated_at=datetime.now(timezone.utc).isoformat(),
        week3_passed=False,
        week4_passed=False,
        all_passed=False,
    )

    # --- Week 3: 数据管道与趋势监控 ---
    readiness = check_readiness(cfg)
    report.checks.append(
        CheckItem(
            week=3,
            category="readiness",
            name="数据就绪度非 demo",
            passed=readiness.tier in ("production", "degraded"),
            detail=f"tier={readiness.tier}",
            evidence=readiness.to_dict(),
        )
    )

    local = load_local_btc_1m_csvs()
    bars = len(local) if local is not None else 0
    report.checks.append(
        CheckItem(
            week=3,
            category="data_pipeline",
            name="本地 BTC 1m 数据",
            passed=bars >= 500,
            detail=f"{bars} bars",
            evidence={"bars": bars},
        )
    )

    sched = SchedulerMetaStore().status()
    tasks_ok = int(sched.get("tasks_ok") or 0)
    task_count = int(sched.get("task_count") or 0)
    report.checks.append(
        CheckItem(
            week=3,
            category="data_pipeline",
            name="调度器任务有成功记录",
            passed=tasks_ok > 0 or task_count == 0,
            detail=f"{tasks_ok}/{task_count} ok",
            evidence=sched,
        )
    )

    store = SnapshotStore()
    health = run_trend_health_check(cfg, store=store)
    report.checks.append(
        CheckItem(
            week=3,
            category="trend_monitor",
            name="趋势健康非 critical",
            passed=health.get("status") != "critical",
            detail=f"status={health.get('status')}",
            evidence={
                "status": health.get("status"),
                "findings": health.get("findings"),
            },
        )
    )

    tj = health.get("trend_judgment") or {}
    report.checks.append(
        CheckItem(
            week=3,
            category="trend_monitor",
            name="trend_judgment 契约存在",
            passed=bool(tj.get("trend")),
            detail=f"trend={tj.get('trend')}",
            evidence={"keys": sorted(tj.keys())},
        )
    )

    cap = assess_data_capabilities(cfg)
    report.checks.append(
        CheckItem(
            week=3,
            category="data_pipeline",
            name="数据源能力评估",
            passed=cap.get("tier") in ("production", "degraded", "demo"),
            detail=f"cap_tier={cap.get('tier')}",
            evidence=cap,
        )
    )

    # --- Week 4: 反馈闭环与上线门禁 ---
    feedback = build_feedback_stats(symbol=cfg.symbol, cfg=cfg)
    report.checks.append(
        CheckItem(
            week=4,
            category="feedback",
            name="反馈统计 API 数据可用",
            passed="judgment_count" in feedback,
            detail=feedback.get("message", ""),
            evidence=feedback,
        )
    )

    report.checks.append(
        CheckItem(
            week=4,
            category="feedback",
            name="人工判断样本积累",
            passed=feedback["judgment_count"] > 0,
            detail=f"{feedback['judgment_count']}/{RECOMMENDATION_MIN_JUDGMENTS}",
            evidence={
                "judgment_count": feedback["judgment_count"],
                "forward_scored_count": feedback["forward_scored_count"],
            },
        )
    )

    rec_ready = feedback.get("recommendation_ready")
    rec_env = cfg.regime_use_recommendation
    report.checks.append(
        CheckItem(
            week=4,
            category="feedback",
            name="推荐模型就绪或 env 关闭",
            passed=(not rec_env) or rec_ready,
            detail=(
                "recommendation_ready"
                if rec_ready
                else "REGIME_USE_RECOMMENDATION=true 但样本未达标"
            ),
            evidence={
                "regime_use_recommendation": rec_env,
                "recommendation_ready": rec_ready,
            },
        )
    )

    from ai_trade_advisor.ops.production_gate import run_production_gate

    gate = run_production_gate(cfg, require_production=False)
    report.checks.append(
        CheckItem(
            week=4,
            category="production_gate",
            name="生产门禁无阻断项",
            passed=gate.get("passed", False),
            detail="; ".join(gate.get("blockers") or []) or "ok",
            evidence=gate,
        )
    )

    w3 = [c for c in report.checks if c.week == 3]
    w4 = [c for c in report.checks if c.week == 4]
    report.week3_passed = all(c.passed for c in w3)
    report.week4_passed = all(c.passed for c in w4)
    report.all_passed = report.week3_passed and report.week4_passed
    return report

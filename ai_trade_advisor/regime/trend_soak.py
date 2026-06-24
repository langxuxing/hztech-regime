"""趋势判断 soak 测试：长时间采样健康检查并汇总。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.regime.trend_health import run_trend_health_check


def sample_from_health(health: dict[str, Any]) -> dict[str, Any]:
    tj = health.get("trend_judgment") or {}
    return {
        "at": health.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "status": health.get("status"),
        "readiness_tier": health.get("readiness_tier"),
        "snapshot_age_sec": health.get("snapshot_age_sec"),
        "trend": tj.get("trend"),
        "stability": tj.get("stability"),
        "regime_id": tj.get("regime_id"),
        "needs_human_judgment": tj.get("needs_human_judgment"),
        "findings_count": len(health.get("findings") or []),
        "regime_flips_recent": health.get("regime_flips_recent"),
    }


def collect_soak_sample(cfg: AdvisorConfig | None = None, **health_kwargs: Any) -> dict[str, Any]:
    health = run_trend_health_check(cfg, **health_kwargs)
    return sample_from_health(health)


def summarize_soak_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {
            "sample_count": 0,
            "passed": False,
            "status": "critical",
            "message": "无采样数据",
            "status_counts": {},
            "critical_rate": 1.0,
            "degraded_rate": 0.0,
            "ok_rate": 0.0,
            "max_critical_streak": 0,
            "trend_distribution": {},
            "stability_distribution": {},
        }

    status_counts: dict[str, int] = {}
    trend_dist: dict[str, int] = {}
    stability_dist: dict[str, int] = {}
    max_critical_streak = 0
    current_critical = 0

    for s in samples:
        status = str(s.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        trend = str(s.get("trend") or "unknown")
        trend_dist[trend] = trend_dist.get(trend, 0) + 1
        stability = str(s.get("stability") or "unknown")
        stability_dist[stability] = stability_dist.get(stability, 0) + 1
        if status == "critical":
            current_critical += 1
            max_critical_streak = max(max_critical_streak, current_critical)
        else:
            current_critical = 0

    n = len(samples)
    critical_rate = status_counts.get("critical", 0) / n
    degraded_rate = status_counts.get("degraded", 0) / n
    ok_rate = status_counts.get("ok", 0) / n

    passed = critical_rate == 0 and degraded_rate <= 0.2
    if critical_rate > 0:
        overall = "critical"
        message = f"出现 {status_counts.get('critical', 0)} 次 critical 采样"
    elif degraded_rate > 0.2:
        overall = "degraded"
        message = f"degraded 占比 {degraded_rate:.0%} 超过 20%"
    else:
        overall = "ok"
        message = f"soak 通过：{n} 次采样，ok {ok_rate:.0%}"

    return {
        "sample_count": n,
        "passed": passed,
        "status": overall,
        "message": message,
        "status_counts": status_counts,
        "critical_rate": round(critical_rate, 4),
        "degraded_rate": round(degraded_rate, 4),
        "ok_rate": round(ok_rate, 4),
        "max_critical_streak": max_critical_streak,
        "trend_distribution": trend_dist,
        "stability_distribution": stability_dist,
        "first_at": samples[0].get("at"),
        "last_at": samples[-1].get("at"),
    }

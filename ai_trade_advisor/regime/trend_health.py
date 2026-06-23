"""趋势判断健康检查（API / 脚本共用）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.readiness import get_cached_readiness_tier
from ai_trade_advisor.regime.history import RegimeHistoryStore
from ai_trade_advisor.snapshot.store import SnapshotStore, snapshot_key


def run_trend_health_check(
    cfg: AdvisorConfig | None = None,
    *,
    store: SnapshotStore | None = None,
    regime_store: RegimeHistoryStore | None = None,
) -> dict[str, Any]:
    cfg = cfg or AdvisorConfig.from_env()
    store = store or SnapshotStore()
    regime_store = regime_store or RegimeHistoryStore()
    key = snapshot_key(cfg)
    bundle = store.get(key)

    findings: list[dict[str, str]] = []
    status = "ok"

    if bundle is None:
        findings.append({"severity": "critical", "title": "无雷达快照", "detail": f"key={key}"})
        status = "critical"
    else:
        stale = store.is_stale(key, cfg.snapshot_stale_sec)
        if stale:
            findings.append({
                "severity": "high",
                "title": "快照过期",
                "detail": f"超过 {cfg.snapshot_stale_sec}s 未更新",
            })
            status = "degraded"

        tj = bundle.get("trend_judgment")
        if not tj:
            findings.append({
                "severity": "medium",
                "title": "缺少 trend_judgment",
                "detail": "请升级 snapshot-worker",
            })
            if status == "ok":
                status = "degraded"
        else:
            if tj.get("needs_human_judgment"):
                findings.append({
                    "severity": "info",
                    "title": "模型分歧",
                    "detail": "needs_human_judgment=true",
                })
            if tj.get("stability") == "provisional":
                findings.append({
                    "severity": "info",
                    "title": "趋势未确认",
                    "detail": (
                        f"live={tj.get('live_regime_id')} "
                        f"confirmed={tj.get('confirmed_regime_id')}"
                    ),
                })
            if tj.get("hmm_disagrees"):
                findings.append({
                    "severity": "info",
                    "title": "HMM 趋势分歧",
                    "detail": "hmm_disagrees=true",
                })

    history: list[dict[str, Any]] = []
    try:
        history = regime_store.recent(symbol=cfg.symbol, limit=48)
    except Exception as exc:
        findings.append({
            "severity": "high",
            "title": "Regime 历史查询失败",
            "detail": str(exc),
        })
        if status == "ok":
            status = "degraded"

    flips = 0
    prev = None
    for row in reversed(history):
        rid = row.get("regime_id")
        if prev and rid != prev:
            flips += 1
        prev = rid
    if flips > cfg.trend_health_regime_flip_threshold:
        findings.append({
            "severity": "medium",
            "title": "Regime 翻转频繁",
            "detail": f"近 {len(history)} 条历史翻转 {flips} 次",
        })
        if status == "ok":
            status = "degraded"

    readiness_tier = get_cached_readiness_tier(cfg)

    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "readiness_tier": readiness_tier,
        "snapshot_key": key,
        "snapshot_present": bundle is not None,
        "snapshot_age_sec": store.age_seconds(key),
        "snapshot_stale_sec": cfg.snapshot_stale_sec,
        "trend_judgment": (bundle or {}).get("trend_judgment"),
        "regime_flips_recent": flips,
        "regime_history_size": len(history),
        "findings": findings,
    }

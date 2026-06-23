#!/usr/bin/env python3
"""趋势判断健康检查：快照新鲜度、趋势翻转频率、人工判断触发率。"""
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
from ai_trade_advisor.readiness import check_readiness
from ai_trade_advisor.regime.history import RegimeHistoryStore
from ai_trade_advisor.snapshot.store import SnapshotStore, snapshot_key
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def run_health_check(cfg: AdvisorConfig | None = None) -> dict:
    cfg = cfg or AdvisorConfig.from_env()
    readiness = check_readiness(cfg)
    store = SnapshotStore()
    key = snapshot_key(cfg)
    bundle = store.get(key)

    findings: list[dict] = []
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
                    "detail": f"live={tj.get('live_regime_id')} confirmed={tj.get('confirmed_regime_id')}",
                })

    history = RegimeHistoryStore().recent(symbol=cfg.symbol, limit=48)
    flips = 0
    prev = None
    for row in reversed(history):
        rid = row.get("regime_id")
        if prev and rid != prev:
            flips += 1
        prev = rid
    if flips > 6:
        findings.append({
            "severity": "medium",
            "title": "Regime 翻转频繁",
            "detail": f"近 48 条历史翻转 {flips} 次",
        })
        if status == "ok":
            status = "degraded"

    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "readiness_tier": readiness.tier,
        "snapshot_key": key,
        "snapshot_present": bundle is not None,
        "trend_judgment": (bundle or {}).get("trend_judgment"),
        "regime_flips_48h": flips,
        "findings": findings,
    }


def main() -> int:
    report = run_health_check()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    out = get_data_root() / "exports" / "reviews" / "trend_health_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["status"] != "critical" else 1


if __name__ == "__main__":
    raise SystemExit(main())

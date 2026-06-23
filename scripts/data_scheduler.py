#!/usr/bin/env python3
"""统一数据调度器：BTC 1m / 日同步 / 事件扫描 / 反馈校准。"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.bigevent.engine import run_event_analysis
from ai_trade_advisor.bigevent.store import EventStore
from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.paths import ensure_data_layout
from ai_trade_advisor.datasource.scheduler_meta import SchedulerMetaStore
from ai_trade_advisor.regime.feedback.calibrator import run_calibration
from ai_trade_advisor.regime.feedback.store import FeedbackStore
from ai_trade_advisor.regime.feedback.worker import run_forward_scoring_batch

FETCH_SCRIPT = ROOT / "scripts" / "okx_btc_fetch.py"
SYNC_SCRIPT = ROOT / "scripts" / "sync-all-data.sh"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def _run_subprocess(cmd: list[str], *, cwd: Path | None = None) -> tuple[bool, str]:
    proc = subprocess.run(cmd, cwd=cwd or ROOT, check=False)
    ok = proc.returncode == 0
    detail = f"exit {proc.returncode}"
    return ok, detail


def task_btc_1m(cfg: AdvisorConfig, meta: SchedulerMetaStore) -> None:
    t0 = time.perf_counter()
    python = sys.executable
    out_dir = os.environ.get("BTC_1M_OUT_DIR", "")
    cmd = [
        python,
        str(FETCH_SCRIPT),
        "--bar",
        "1m",
        "--incremental",
        "--no-proxy",
    ]
    if out_dir:
        cmd.extend(["--out-dir", out_dir])
    proxy = os.environ.get("BTC_1M_PROXY", "").strip()
    if proxy:
        cmd = [c for c in cmd if c != "--no-proxy"]
        cmd.extend(["--proxy", proxy])
    ok, detail = _run_subprocess(cmd)
    meta.record(
        "btc_1m",
        ok=ok,
        duration_ms=int((time.perf_counter() - t0) * 1000),
        detail=detail,
        error=None if ok else detail,
    )


def task_daily_sync(meta: SchedulerMetaStore) -> None:
    t0 = time.perf_counter()
    ok, detail = _run_subprocess(["bash", str(SYNC_SCRIPT)])
    meta.record(
        "daily_sync",
        ok=ok,
        duration_ms=int((time.perf_counter() - t0) * 1000),
        detail=detail,
        error=None if ok else detail,
    )
    if ok:
        pid_dir = ROOT / "data" / "run"
        pid_dir.mkdir(parents=True, exist_ok=True)
        (pid_dir / "sync.last").write_text(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            encoding="utf-8",
        )


def task_events(cfg: AdvisorConfig, meta: SchedulerMetaStore) -> None:
    t0 = time.perf_counter()
    try:
        snap = run_event_analysis(cfg, store=EventStore())
        detail = f"breaking={len(snap.breaking_events)} calendar={len(snap.calendar_events)}"
        meta.record(
            "events",
            ok=True,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            detail=detail,
        )
    except Exception as exc:
        meta.record(
            "events",
            ok=False,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            error=str(exc),
        )


def task_feedback(cfg: AdvisorConfig, meta: SchedulerMetaStore) -> None:
    t0 = time.perf_counter()
    store = FeedbackStore()
    try:
        fwd = run_forward_scoring_batch(cfg, store=store)
        cal = run_calibration(cfg, store=store)
        detail = f"forward={fwd.get('processed')} calibrated={cal.get('activated')}"
        meta.record(
            "regime_feedback",
            ok=True,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            detail=detail,
        )
    except Exception as exc:
        meta.record(
            "regime_feedback",
            ok=False,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            error=str(exc),
        )


def _should_run_daily(now: datetime, last_run: date | None, hour: int, minute: int) -> bool:
    if now.hour != hour or now.minute != minute:
        return False
    today = now.date()
    return last_run != today


def main() -> int:
    _load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = AdvisorConfig.from_env()
    meta = SchedulerMetaStore()
    ensure_data_layout()

    btc_interval = max(cfg.sched_btc_1m_sec, 60)
    events_interval = max(cfg.sched_events_sec, 60)
    tz = ZoneInfo(cfg.sched_sync_timezone)
    sync_hour = cfg.sched_sync_hour
    sync_minute = cfg.sched_sync_minute
    feedback_interval_h = max(cfg.regime_calibration_interval_hours, 1)

    logging.info(
        "数据调度器启动：btc_1m=%ds events=%ds sync=%02d:%02d %s feedback=%dh",
        btc_interval,
        events_interval,
        sync_hour,
        sync_minute,
        cfg.sched_sync_timezone,
    )

    last_btc = 0.0
    last_events = 0.0
    last_feedback = 0.0
    last_sync_day: date | None = None

    if os.environ.get("SCHED_ON_START", "1").strip().lower() in {"1", "true", "yes"}:
        logging.info("SCHED_ON_START=1，立即执行 btc_1m + events")
        task_btc_1m(cfg, meta)
        task_events(cfg, meta)
        last_btc = time.monotonic()
        last_events = time.monotonic()

    while True:
        now_mono = time.monotonic()
        cfg = AdvisorConfig.from_env()

        if now_mono - last_btc >= btc_interval:
            task_btc_1m(cfg, meta)
            last_btc = now_mono

        if now_mono - last_events >= events_interval:
            task_events(cfg, meta)
            last_events = now_mono

        if now_mono - last_feedback >= feedback_interval_h * 3600:
            task_feedback(cfg, meta)
            last_feedback = now_mono

        now_local = datetime.now(tz)
        if _should_run_daily(now_local, last_sync_day, sync_hour, sync_minute):
            logging.info("触发日同步 (%s)", now_local.date().isoformat())
            task_daily_sync(meta)
            last_sync_day = now_local.date()

        time.sleep(5)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n数据调度器已停止", file=sys.stderr)
        raise SystemExit(0)

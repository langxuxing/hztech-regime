#!/usr/bin/env python3
"""每日定点数据同步调度器（stdlib，无额外依赖）。"""
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
SYNC_SCRIPT = ROOT / "scripts" / "sync-all-data.sh"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def _sync_schedule() -> tuple[int, int, ZoneInfo]:
    hour = int(os.environ.get("SYNC_HOUR", "8"))
    minute = int(os.environ.get("SYNC_MINUTE", "0"))
    tz_name = os.environ.get("SYNC_TIMEZONE", "Asia/Shanghai")
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"非法同步时间: {hour:02d}:{minute:02d}")
    return hour, minute, ZoneInfo(tz_name)


def _run_sync() -> int:
    proc = subprocess.run(
        ["bash", str(SYNC_SCRIPT)],
        cwd=ROOT,
        check=False,
    )
    return int(proc.returncode)


def main() -> int:
    _load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        hour, minute, tz = _sync_schedule()
    except Exception as exc:
        logging.error("配置错误: %s", exc)
        return 1

    if not SYNC_SCRIPT.is_file():
        logging.error("同步脚本不存在: %s", SYNC_SCRIPT)
        return 1

    logging.info(
        "数据同步调度器已启动：每天 %02d:%02d (%s)",
        hour,
        minute,
        tz,
    )

    last_run: date | None = None

    if os.environ.get("SYNC_ON_START", "0").strip() in {"1", "true", "yes"}:
        logging.info("SYNC_ON_START=1，立即执行一次同步")
        code = _run_sync()
        logging.info("启动同步结束 (exit %s)", code)
        last_run = datetime.now(tz).date()

    while True:
        now = datetime.now(tz)
        if now.hour == hour and now.minute == minute:
            today = now.date()
            if last_run != today:
                logging.info("触发定时同步 (%s)", today.isoformat())
                code = _run_sync()
                logging.info("定时同步结束 (exit %s)", code)
                last_run = today
        time.sleep(30)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n调度器已停止", file=sys.stderr)
        raise SystemExit(0)

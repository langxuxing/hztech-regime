#!/usr/bin/env python3
"""每 N 秒增量拉取 BTC 1m 标记价格 K 线（stdlib，无额外依赖）。"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FETCH_SCRIPT = ROOT / "scripts" / "okx_btc_fetch.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_trade_advisor.datasource.paths import get_ohlcv_dir


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def _interval_sec() -> int:
    sec = int(os.environ.get("BTC_1M_INTERVAL_SEC", "300"))
    if sec < 60:
        raise ValueError(f"BTC_1M_INTERVAL_SEC 须 >= 60，当前: {sec}")
    return sec


def _run_fetch() -> int:
    python = sys.executable
    out_dir = os.environ.get("BTC_1M_OUT_DIR", str(get_ohlcv_dir("Btc")))
    cmd = [
        python,
        str(FETCH_SCRIPT),
        "--bar",
        "1m",
        "--incremental",
        "--out-dir",
        out_dir,
        "--no-proxy",
    ]
    proxy = os.environ.get("BTC_1M_PROXY", "").strip()
    if proxy:
        cmd = cmd[:-1]  # drop --no-proxy
        cmd.extend(["--proxy", proxy])
    proc = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(proc.returncode)


def main() -> int:
    _load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        interval = _interval_sec()
    except Exception as exc:
        logging.error("配置错误: %s", exc)
        return 1

    if not FETCH_SCRIPT.is_file():
        logging.error("下载脚本不存在: %s", FETCH_SCRIPT)
        return 1

    logging.info("BTC 1m 数据调度器已启动：每 %d 秒增量拉取一次", interval)

    if os.environ.get("BTC_1M_ON_START", "1").strip().lower() in {"1", "true", "yes"}:
        logging.info("BTC_1M_ON_START=1，立即执行一次下载")
        code = _run_fetch()
        logging.info("启动下载结束 (exit %s)", code)

    while True:
        started = time.monotonic()
        code = _run_fetch()
        logging.info("定时下载结束 (exit %s)", code)
        elapsed = time.monotonic() - started
        sleep_sec = max(0.0, interval - elapsed)
        if sleep_sec > 0:
            time.sleep(sleep_sec)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nBTC 1m 调度器已停止", file=sys.stderr)
        raise SystemExit(0)

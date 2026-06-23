#!/usr/bin/env python3
"""后台快照 worker：定时计算并写入缓存。"""

from __future__ import annotations

import argparse
import signal
import time

from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.paths import ensure_data_layout
from ai_trade_advisor.snapshot.bundle import refresh_snapshot
from ai_trade_advisor.snapshot.store import SnapshotStore, snapshot_key


_stop = False


def _handle_sigterm(*_args) -> None:
    global _stop
    _stop = True


def run_once(
    cfg: AdvisorConfig,
    store: SnapshotStore,
    *,
    skip_orderbook: bool = False,
    skip_capital_flows: bool = False,
) -> dict:
    bundle = refresh_snapshot(
        cfg,
        store,
        skip_orderbook=skip_orderbook,
        skip_capital_flows=skip_capital_flows,
    )
    print(
        f"[snapshot-worker] {snapshot_key(cfg)} "
        f"v={bundle.get('version')} as_of={bundle.get('as_of')}"
    )
    return bundle


def run_loop(
    cfg: AdvisorConfig,
    *,
    interval_sec: int,
    skip_orderbook: bool = False,
    skip_capital_flows: bool = False,
) -> None:
    store = SnapshotStore()
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    while not _stop:
        try:
            run_once(
                cfg,
                store,
                skip_orderbook=skip_orderbook,
                skip_capital_flows=skip_capital_flows,
            )
        except Exception as exc:
            print(f"[snapshot-worker] 错误: {exc}")
        for _ in range(max(interval_sec, 30)):
            if _stop:
                break
            time.sleep(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regime & Trend 快照 Worker")
    parser.add_argument("--once", action="store_true", help="只运行一次后退出")
    parser.add_argument("--skip-orderbook", action="store_true")
    parser.add_argument("--skip-capital-flows", action="store_true")
    args = parser.parse_args(argv)

    layout = ensure_data_layout()
    print(f"快照目录: {layout['cache'] / 'snapshots'}")

    cfg = AdvisorConfig.from_env()
    store = SnapshotStore()

    if args.once:
        run_once(
            cfg,
            store,
            skip_orderbook=args.skip_orderbook,
            skip_capital_flows=args.skip_capital_flows,
        )
        return 0

    run_loop(
        cfg,
        interval_sec=cfg.snapshot_poll_interval_sec,
        skip_orderbook=args.skip_orderbook,
        skip_capital_flows=args.skip_capital_flows,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env bash
# 启动 BTC 1m 数据定时下载（默认每 5 分钟）
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"
cd "$ROOT"

ensure_pid_dir
ensure_env

if is_running "$BTC_1M_PID_FILE"; then
  log "BTC 1m 调度器已在运行 (pid $(cat "$BTC_1M_PID_FILE"))"
  log "  间隔: 每 ${BTC_1M_INTERVAL_SEC}s"
  log "  日志: $PID_DIR/btc-1m-scheduler.log"
  exit 0
fi

activate_venv

log "启动 BTC 1m 数据调度器 → 每 ${BTC_1M_INTERVAL_SEC}s 增量拉取"
pid="$(run_detached "$PID_DIR/btc-1m-scheduler.log" \
  env BTC_1M_INTERVAL_SEC="$BTC_1M_INTERVAL_SEC" BTC_1M_ON_START="${BTC_1M_ON_START:-1}" \
      BTC_1M_OUT_DIR="${BTC_1M_OUT_DIR:-$ROOT/data/OHLCV/Btc}" \
      BTC_1M_PROXY="${BTC_1M_PROXY:-}" \
  python "$ROOT/scripts/btc_1m_scheduler.py")"
echo "$pid" >"$BTC_1M_PID_FILE"
log "BTC 1m 调度器已启动 (pid $pid)"
log "  手动下载: ./scripts/download_btc.sh --bar 1m --incremental --no-proxy"
log "  日志:     $PID_DIR/btc-1m-scheduler.log"
log "  停止:     ./scripts/stop-btc-1m-scheduler.sh"

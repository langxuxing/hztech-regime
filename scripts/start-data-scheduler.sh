#!/usr/bin/env bash
# 启动统一数据调度器（BTC 1m / 事件 / 日同步 / 反馈）
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"
cd "$ROOT"

DATA_SCHEDULER_PID_FILE="${PID_DIR}/data-scheduler.pid"
DATA_SCHEDULER_LOG="${PID_DIR}/data-scheduler.log"

ensure_pid_dir
ensure_env

if is_running "$DATA_SCHEDULER_PID_FILE"; then
  log "Data Scheduler 已在运行 (pid $(cat "$DATA_SCHEDULER_PID_FILE"))"
  log "  日志: $DATA_SCHEDULER_LOG"
  exit 0
fi

activate_venv

log "启动 Data Scheduler"
pid="$(run_detached "$DATA_SCHEDULER_LOG" python "$ROOT/scripts/data_scheduler.py")"
echo "$pid" >"$DATA_SCHEDULER_PID_FILE"

log "  PID:  $pid"
log "  日志: $DATA_SCHEDULER_LOG"
log "  停止: ./scripts/stop-data-scheduler.sh"

#!/usr/bin/env bash
# 一键启动：快照 worker + API + Flutter Web 看板
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"

log "=== Regime & Trend 本地启动 ==="

# 首次运行自动 setup
if [[ ! -d "$VENV" ]] || [[ ! -f "$VENV/bin/activate" ]]; then
  log "首次运行，执行 setup..."
  "$ROOT/scripts/setup.sh"
fi

# 计算与 API 分离：worker 负责定时刷新，API 只读缓存
export POLL_SNAPSHOTS="${POLL_SNAPSHOTS:-0}"
ensure_env
"$ROOT/scripts/start-data-scheduler.sh"

if [[ "${SCHED_ON_START:-1}" =~ ^(1|true|yes)$ ]]; then
  log "等待调度器首次任务 (btc_1m + events)..."
  if wait_scheduler_first_run 45; then
    log "调度器首次任务已完成:"
    print_scheduler_tasks
    log "调度器日志:"
    tail_scheduler_log 10
  else
    log "调度器仍在执行首次任务，查看日志: $DATA_SCHEDULER_LOG"
    tail_scheduler_log 5
  fi
fi

"$ROOT/scripts/start-snapshot-worker.sh"
"$ROOT/scripts/start-api.sh"
"$ROOT/scripts/start-dashboard.sh"

log ""
log "=== 服务已启动 ==="
log "  API:       http://${API_HOST}:${API_PORT}"
log "  看板:      http://localhost:${WEB_PORT}"
log "  数据:      $ROOT/data"
log "  停止:      ./scripts/stop-all.sh"
log "  Scheduler: $(scheduler_config_line)"
log "  Scheduler: $DATA_SCHEDULER_LOG"
log "  API 日志:  $PID_DIR/api.log"
log "  Worker:    $PID_DIR/snapshot-worker.log"
log "  Web 日志:  $PID_DIR/web.log"

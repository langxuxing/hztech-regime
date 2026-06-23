#!/usr/bin/env bash
# 启动每日定点数据同步调度器
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"
cd "$ROOT"

ensure_pid_dir
ensure_env

if is_running "$SYNC_PID_FILE"; then
  log "同步调度器已在运行 (pid $(cat "$SYNC_PID_FILE"))"
  log "  计划: 每天 $(printf '%02d:%02d' "$SYNC_HOUR" "$SYNC_MINUTE") (${SYNC_TIMEZONE})"
  log "  日志: $PID_DIR/sync-scheduler.log"
  exit 0
fi

activate_venv

log "启动数据同步调度器 → 每天 $(printf '%02d:%02d' "$SYNC_HOUR" "$SYNC_MINUTE") (${SYNC_TIMEZONE})"
pid="$(run_detached "$PID_DIR/sync-scheduler.log" \
  env SYNC_HOUR="$SYNC_HOUR" SYNC_MINUTE="$SYNC_MINUTE" SYNC_TIMEZONE="$SYNC_TIMEZONE" \
      SYNC_ON_START="${SYNC_ON_START:-0}" \
  python "$ROOT/scripts/sync_scheduler.py")"
echo "$pid" >"$SYNC_PID_FILE"
log "同步调度器已启动 (pid $pid)"
log "  手动同步: ./sync.sh"
log "  日志:     $PID_DIR/sync-scheduler.log / $PID_DIR/sync.log"
log "  停止:     ./scripts/stop-sync-scheduler.sh"

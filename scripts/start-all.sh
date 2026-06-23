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
"$ROOT/scripts/start-snapshot-worker.sh"
"$ROOT/scripts/start-api.sh"
"$ROOT/scripts/start-dashboard.sh"

log ""
log "=== 服务已启动 ==="
log "  API:     http://${API_HOST}:${API_PORT}"
log "  看板:    http://localhost:${WEB_PORT}"
log "  数据:    $ROOT/data"
log "  停止:    ./scripts/stop-all.sh"
log "  API 日志: $PID_DIR/api.log"
log "  Worker:  $PID_DIR/snapshot-worker.log"
log "  Web 日志: $PID_DIR/web.log"

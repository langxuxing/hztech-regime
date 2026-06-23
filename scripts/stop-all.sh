#!/usr/bin/env bash
# 停止 API 与 Flutter Web 看板
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"

log "停止服务..."

stop_by_pid_file "API" "$API_PID_FILE"
stop_by_pid_file "Web" "$WEB_PID_FILE"
stop_by_pid_file "快照 worker" "$PID_DIR/snapshot-worker.pid"

# 兜底：按端口清理残留进程
stop_by_port "$API_PORT"
stop_by_port "$WEB_PORT"

log "已全部停止"

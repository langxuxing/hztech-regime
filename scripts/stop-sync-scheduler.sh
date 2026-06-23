#!/usr/bin/env bash
# 停止数据同步调度器
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"

log "停止数据同步调度器..."
stop_by_pid_file "Sync Scheduler" "$SYNC_PID_FILE"
log "已停止"

#!/usr/bin/env bash
# 停止 BTC 1m 数据定时下载
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"

log "停止 BTC 1m 调度器..."
stop_by_pid_file "BTC 1m Scheduler" "$BTC_1M_PID_FILE"
log "已停止"

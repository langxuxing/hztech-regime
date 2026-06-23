#!/usr/bin/env bash
# 停止统一数据调度器
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"

DATA_SCHEDULER_PID_FILE="${PID_DIR}/data-scheduler.pid"
stop_by_pid_file "Data Scheduler" "$DATA_SCHEDULER_PID_FILE"

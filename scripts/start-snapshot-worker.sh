#!/usr/bin/env bash
# 独立快照 worker（与 API 分离部署时使用）
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"
cd "$ROOT"

ensure_pid_dir
ensure_env
activate_venv
init_data_dirs

SNAPSHOT_PID_FILE="$PID_DIR/snapshot-worker.pid"

if is_running "$SNAPSHOT_PID_FILE"; then
  log "快照 worker 已在运行 (pid $(cat "$SNAPSHOT_PID_FILE"))"
  exit 0
fi

EXTRA_ARGS=()
if [[ "${SKIP_ORDERBOOK:-1}" == "1" ]]; then
  EXTRA_ARGS+=(--skip-orderbook)
fi

log "启动快照 worker"
pid="$(run_detached "$PID_DIR/snapshot-worker.log" python -m ai_trade_advisor.snapshot.worker \
  "${EXTRA_ARGS[@]}")"
echo "$pid" >"$SNAPSHOT_PID_FILE"
log "快照 worker 已启动 (pid $pid)，日志: $PID_DIR/snapshot-worker.log"

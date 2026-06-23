#!/usr/bin/env bash
# 启动 Flask API 服务
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"
cd "$ROOT"

ensure_pid_dir
ensure_env

if is_running "$API_PID_FILE"; then
  log "API 已在运行 (pid $(cat "$API_PID_FILE")) → http://${API_HOST}:${API_PORT}"
  exit 0
fi

activate_venv
init_data_dirs

EXTRA_ARGS=()
if [[ "${SKIP_ORDERBOOK:-1}" == "1" ]]; then
  EXTRA_ARGS+=(--skip-orderbook)
fi
if [[ "${POLL_EVENTS:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--poll-events)
fi

# 快照：默认由独立 worker 负责；仅 POLL_SNAPSHOTS=1 时由 API 内嵌轮询
if [[ "${POLL_SNAPSHOTS:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--poll-snapshots)
else
  EXTRA_ARGS+=(--no-poll-snapshots)
fi

if [[ "${SNAPSHOT_WARMUP_ON_START:-1}" == "1" ]]; then
  EXTRA_ARGS+=(--warmup-snapshot)
else
  EXTRA_ARGS+=(--no-warmup-snapshot)
fi

log "启动 API → http://${API_HOST}:${API_PORT}"
pid="$(run_detached "$PID_DIR/api.log" python -m ai_trade_advisor.api_server \
  --host "$API_HOST" \
  --port "$API_PORT" \
  "${EXTRA_ARGS[@]}")"
echo "$pid" >"$API_PID_FILE"

if wait_for_url "http://${API_HOST}:${API_PORT}/health" 30; then
  log "API 就绪: http://${API_HOST}:${API_PORT}/health"
else
  log "API 启动超时，查看日志: $PID_DIR/api.log"
  tail -20 "$PID_DIR/api.log" || true
  exit 1
fi

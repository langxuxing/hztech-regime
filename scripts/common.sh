#!/usr/bin/env bash
# 公共变量与函数（被其他脚本 source）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
PID_DIR="$ROOT/data/run"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8765}"
WEB_PORT="${WEB_PORT:-8080}"
API_PID_FILE="$PID_DIR/api.pid"
WEB_PID_FILE="$PID_DIR/web.pid"
SYNC_PID_FILE="$PID_DIR/sync-scheduler.pid"
BTC_1M_PID_FILE="$PID_DIR/btc-1m-scheduler.pid"
DATA_SCHEDULER_PID_FILE="$PID_DIR/data-scheduler.pid"

# 数据同步定时器（scripts/start-sync-scheduler.sh）
SYNC_HOUR="${SYNC_HOUR:-8}"
SYNC_MINUTE="${SYNC_MINUTE:-0}"
SYNC_TIMEZONE="${SYNC_TIMEZONE:-Asia/Shanghai}"
SYNC_ON_START="${SYNC_ON_START:-0}"

# BTC 1m 定时下载（scripts/start-btc-1m-scheduler.sh）
BTC_1M_INTERVAL_SEC="${BTC_1M_INTERVAL_SEC:-300}"
BTC_1M_ON_START="${BTC_1M_ON_START:-1}"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die() { log "ERROR: $*"; exit 1; }

ensure_pid_dir() {
  mkdir -p "$PID_DIR"
}

activate_venv() {
  [[ -f "$VENV/bin/activate" ]] || die "虚拟环境不存在，请先运行: ./scripts/setup.sh"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
}

ensure_env() {
  if [[ ! -f "$ROOT/.env" ]]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    log "已从 .env.example 创建 .env"
  fi
}

init_data_dirs() {
  activate_venv
  python - <<'PY'
from ai_trade_advisor.datasource.paths import ensure_data_layout
layout = ensure_data_layout()
print(f"数据目录: {layout['root']}")
PY
}

wait_for_url() {
  local url="$1"
  local retries="${2:-30}"
  local i
  for ((i = 1; i <= retries; i++)); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file")"
  kill -0 "$pid" 2>/dev/null
}

stop_by_pid_file() {
  local name="$1"
  local pid_file="$2"
  if is_running "$pid_file"; then
    local pid
    pid="$(cat "$pid_file")"
    kill "$pid" 2>/dev/null || true
    sleep 1
    kill -9 "$pid" 2>/dev/null || true
    log "已停止 $name (pid $pid)"
  fi
  rm -f "$pid_file"
}

stop_by_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti:"$port" 2>/dev/null || true)"
  [[ -n "$pids" ]] || return 0
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 1
  # shellcheck disable=SC2086
  kill -9 $pids 2>/dev/null || true
}

# 后台启动进程（macOS / Linux 兼容）
run_detached() {
  local log_file="$1"
  shift
  if command -v setsid >/dev/null 2>&1; then
    setsid nohup "$@" >>"$log_file" 2>&1 < /dev/null &
  else
    nohup "$@" >>"$log_file" 2>&1 < /dev/null &
  fi
  disown 2>/dev/null || true
  echo $!
}

#!/usr/bin/env bash
# 启动 Flutter Web 看板（Chrome，无需 Xcode / iOS / Android）
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"
cd "$ROOT/dashboard"

command -v flutter >/dev/null 2>&1 || die "未安装 Flutter，请先安装: https://flutter.dev"

ensure_pid_dir

if is_running "$WEB_PID_FILE"; then
  log "看板已在运行 (pid $(cat "$WEB_PID_FILE")) → http://localhost:${WEB_PORT}"
  exit 0
fi

# 确保 API 可用（可选等待）
if ! curl -sf "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
  log "API 未运行，先启动后端..."
  "$ROOT/scripts/start-api.sh"
fi

log "启动 Flutter Web 看板 → http://localhost:${WEB_PORT}"
flutter pub get

# 后台运行 flutter，日志写入 data/run/web.log
pid="$(run_detached "$PID_DIR/web.log" flutter run -d chrome --web-port "$WEB_PORT")"
echo "$pid" >"$WEB_PID_FILE"

log "看板编译中，日志: $PID_DIR/web.log"
log "就绪后访问: http://localhost:${WEB_PORT}"

#!/usr/bin/env bash
# 查看服务运行状态
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"

check() {
  local name="$1"
  local url="$2"
  local pid_file="$3"
  if curl -sf "$url" >/dev/null 2>&1; then
    local pid_info=""
    if [[ -f "$pid_file" ]]; then
      pid_info=" (pid $(cat "$pid_file"))"
    fi
    log "$name: 运行中${pid_info} → $url"
  else
    log "$name: 未运行"
  fi
}

check "API"  "http://${API_HOST}:${API_PORT}/health" "$API_PID_FILE"
check "Web"  "http://localhost:${WEB_PORT}"           "$WEB_PID_FILE"

if is_running "$SYNC_PID_FILE"; then
  log "Sync:  运行中 (pid $(cat "$SYNC_PID_FILE")) → 每天 $(printf '%02d:%02d' "$SYNC_HOUR" "$SYNC_MINUTE") (${SYNC_TIMEZONE})"
else
  log "Sync:  未运行（启动: ./scripts/start-sync-scheduler.sh）"
fi

if is_running "$BTC_1M_PID_FILE"; then
  log "BTC1m: 运行中 (pid $(cat "$BTC_1M_PID_FILE")) → 每 ${BTC_1M_INTERVAL_SEC}s（建议改用 data-scheduler）"
else
  log "BTC1m: 未运行（已合并至 ./scripts/start-data-scheduler.sh）"
fi

if is_running "$DATA_SCHEDULER_PID_FILE"; then
  log "Scheduler: 运行中 (pid $(cat "$DATA_SCHEDULER_PID_FILE"))"
  log "  计划: $(scheduler_config_line)"
  log "  任务:"
  print_scheduler_tasks
else
  log "Scheduler: 未运行（启动: ./scripts/start-data-scheduler.sh）"
fi

if [[ -f "$PID_DIR/sync.last" ]]; then
  log "Sync:  上次成功同步 $(cat "$PID_DIR/sync.last")"
fi

activate_venv 2>/dev/null || true
if [[ -f "$VENV/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  python - <<'PY' 2>/dev/null || true
from ai_trade_advisor.config import AdvisorConfig
from ai_trade_advisor.datasource.capabilities import assess_data_capabilities
from ai_trade_advisor.datasource.ohlcv import load_local_btc_1m_csvs
from ai_trade_advisor.datasource.scheduler_meta import SchedulerMetaStore

cap = assess_data_capabilities(AdvisorConfig.from_env())
local = load_local_btc_1m_csvs()
bars = len(local) if local is not None else 0
meta = SchedulerMetaStore().status()
print(f"数据层级: {cap['tier']} | 本地1m: {bars} bars | 调度任务: {meta.get('tasks_ok', 0)}/{meta.get('task_count', 0)} ok")
PY
fi

#!/usr/bin/env bash
# 一键同步本地数据：宏观 / Farside BTC ETF / BTC 15m K 线 / CoinGlass ETF（可选）
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/common.sh"

ensure_pid_dir
activate_venv
ensure_env

SYNC_LOG="${SYNC_LOG:-$PID_DIR/sync.log}"
SYNC_ETF_DAYS="${SYNC_ETF_DAYS:-14}"
SYNC_OHLCV_DAYS="${SYNC_OHLCV_DAYS:-3}"
SYNC_COINGLASS_DAYS="${SYNC_COINGLASS_DAYS:-7}"
SYNC_SKIP_COINGLASS="${SYNC_SKIP_COINGLASS:-0}"

FAILED=0
STAMP="$(date '+%Y-%m-%d %H:%M:%S')"

exec > >(tee -a "$SYNC_LOG") 2>&1

printf '[%s] === 数据同步开始 ===\n' "$STAMP"

run_step() {
  local name="$1"
  shift
  local t0
  t0="$(date '+%H:%M:%S')"
  printf '[%s] [%s] 开始...\n' "$t0" "$name"
  if "$@"; then
    printf '[%s] [%s] 完成\n' "$(date '+%H:%M:%S')" "$name"
  else
    local code=$?
    printf '[%s] [%s] 失败 (exit %s)\n' "$(date '+%H:%M:%S')" "$name" "$code"
    FAILED=$((FAILED + 1))
  fi
}

run_step "macro" python -m ai_trade_advisor.datasource.macro_cli
run_step "btc-etf-farside" python "$ROOT/scripts/download_farside_etf.py" --days "$SYNC_ETF_DAYS"
# 15m K 线作历史回补；实盘主路径为 btc_1m_scheduler → load_ohlcv resample
run_step "btc-ohlcv-backfill" "$ROOT/scripts/download_btc.sh" --days "$SYNC_OHLCV_DAYS" --no-proxy

if [[ "$SYNC_SKIP_COINGLASS" != "1" ]]; then
  if python - <<'PY'
from ai_trade_advisor.config import AdvisorConfig
cfg = AdvisorConfig.from_env()
raise SystemExit(0 if (cfg.coinglass_api_key or "").strip() else 1)
PY
  then
    run_step "coinglass-etf" "$ROOT/scripts/download_etf.sh" --days "$SYNC_COINGLASS_DAYS"
  else
    printf '[%s] [coinglass-etf] 跳过（未配置 COINGLASS_API_KEY）\n' "$(date '+%H:%M:%S')"
  fi
fi

printf '[%s] === 数据同步结束 (失败 %s 项) ===\n' "$(date '+%H:%M:%S')" "$FAILED"

if [[ "$FAILED" -eq 0 ]]; then
  date '+%Y-%m-%d %H:%M:%S' >"$PID_DIR/sync.last"
fi

exit "$FAILED"

#!/usr/bin/env bash
# 参考 CreativeIdeaLab/OHLCV/download_pepe.sh
# 下载 BTC-USDT-SWAP 15m 标记价格 K 线，按 UTC 自然日分 CSV。
# 用法: ./download_btc.sh --start YYYY-MM-DD --end YYYY-MM-DD [--no-proxy]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FETCH_PY="${SCRIPT_DIR}/okx_btc_fetch.py"
DEFAULT_OUT="${SCRIPT_DIR}/../data/OHLCV/Btc"

PYTHON="python3"
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  if [[ -x "${VIRTUAL_ENV}/bin/python3" ]]; then
    PYTHON="${VIRTUAL_ENV}/bin/python3"
  elif [[ -x "${VIRTUAL_ENV}/bin/python" ]]; then
    PYTHON="${VIRTUAL_ENV}/bin/python"
  fi
fi
if [[ "${PYTHON}" == "python3" ]] && [[ -x "${SCRIPT_DIR}/../.venv/bin/python3" ]]; then
  PYTHON="${SCRIPT_DIR}/../.venv/bin/python3"
fi

START=""
END=""
OUT_DIR="${DEFAULT_OUT}"
PASS_THROUGH=()

usage() {
  echo "用法: $(basename "$0") --start YYYY-MM-DD --end YYYY-MM-DD [--out-dir DIR] [其它 okx_btc_fetch.py 参数]" >&2
  echo "  或: $(basename "$0") --days N [--out-dir DIR]" >&2
  echo "  默认 --out-dir: ${DEFAULT_OUT}" >&2
  echo "  示例: $(basename "$0") --start 2025-01-01 --end 2026-06-21 --no-proxy" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start)
      START="${2:-}"
      shift 2 || true
      ;;
    --end)
      END="${2:-}"
      shift 2 || true
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2 || true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      PASS_THROUGH+=("$1")
      shift
      ;;
  esac
done

if [[ -z "${START}" && -z "${END}" ]]; then
  for ((i=0; i<${#PASS_THROUGH[@]}; i++)); do
    if [[ "${PASS_THROUGH[i]}" == "--days" ]]; then
      break
    fi
  done
  if ! printf '%s\n' "${PASS_THROUGH[@]:-}" | grep -q '^--days$'; then
    usage
    exit 1
  fi
fi

if [[ -n "${START}" && -z "${END}" ]] || [[ -z "${START}" && -n "${END}" ]]; then
  usage
  exit 1
fi

mkdir -p "${OUT_DIR}"

py_args=("${PYTHON}" "${FETCH_PY}" --out-dir "${OUT_DIR}")
if [[ -n "${START}" && -n "${END}" ]]; then
  py_args+=(--start-date "${START}" --end-date "${END}")
fi
if ((${#PASS_THROUGH[@]} > 0)); then
  py_args+=("${PASS_THROUGH[@]}")
fi
exec "${py_args[@]}"

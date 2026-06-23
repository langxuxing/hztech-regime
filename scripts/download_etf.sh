#!/usr/bin/env bash
# 下载 BTC/ETH Spot ETF 日度净流入/流出（CoinGlass，默认近 1 年）
# 用法: ./download_etf.sh [--days 365] [--api-key KEY]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FETCH_PY="${SCRIPT_DIR}/download_etf_flow.py"
DEFAULT_OUT="${SCRIPT_DIR}/../data/ETF"

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

OUT_DIR="${DEFAULT_OUT}"
PASS_THROUGH=()

usage() {
  echo "用法: $(basename "$0") [--days N] [--out-dir DIR] [--api-key KEY]" >&2
  echo "  默认下载 BTC+ETH 近 365 天到 ${DEFAULT_OUT}" >&2
  echo "  需 .env 中 COINGLASS_API_KEY（Hobbyist+）或传 --api-key" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
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

mkdir -p "${OUT_DIR}"

py_args=("${PYTHON}" "${FETCH_PY}" --out-dir "${OUT_DIR}")
if ((${#PASS_THROUGH[@]} > 0)); then
  py_args+=("${PASS_THROUGH[@]}")
fi
exec "${py_args[@]}"

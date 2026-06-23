#!/usr/bin/env bash
# 初始化环境：虚拟环境、依赖、.env、数据目录
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }

log "项目目录: $ROOT"

if [[ ! -d .venv ]]; then
  log "创建 Python 虚拟环境..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

log "安装 Python 依赖..."
pip install -q -e ".[dev]"

log "可选模型依赖（按需安装）:"
log "  LSTM:  pip install -e \".[lstm]\""
log "  TA:    pip install -e \".[ta]\""

if [[ ! -f .env ]]; then
  cp .env.example .env
  log "已创建 .env（可按需编辑 API Key 等配置）"
fi

log "初始化数据目录..."
python - <<'PY'
from ai_trade_advisor.datasource.paths import ensure_data_layout
layout = ensure_data_layout()
for name, path in layout.items():
    print(f"  {name}: {path}")
PY

if command -v flutter >/dev/null 2>&1; then
  log "获取 Flutter 依赖..."
  if ! (cd dashboard && flutter pub get); then
    log "Flutter 依赖获取失败，可稍后手动运行: cd dashboard && flutter pub get"
  fi
else
  log "未检测到 flutter，跳过 dashboard 依赖（Web 看板需安装 Flutter）"
fi

log "完成。启动全部服务: ./scripts/start-all.sh"

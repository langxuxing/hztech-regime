#!/usr/bin/env bash
# 无需 Xcode，在 Chrome 中运行看板（跳过 iOS / Android / macOS 原生构建）
exec "$(dirname "$0")/../scripts/start-dashboard.sh" "$@"

#!/usr/bin/env bash
# 将项目纳入 git 版本管理（不提交 .env / data 等大文件）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .git ]]; then
  git init
  echo "已初始化 git 仓库"
fi

git add -A
git status --short | head -40

echo ""
echo "已 stage 全部受 .gitignore 约束的源码。"
echo "创建首次提交: git commit -m \"Initial commit\""

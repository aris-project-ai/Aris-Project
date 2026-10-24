#!/usr/bin/env bash
# 本地检查入口（AGENTS.md §7）：lint -> format -> mypy -> pytest
# 用法：bash scripts/check.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> ruff check"
uv run ruff check .

echo "==> ruff format --check"
uv run ruff format --check .

echo "==> mypy（core + store）"
uv run mypy src/aris/core src/aris/store

echo "==> pytest"
uv run pytest -q

echo
echo "全部通过。"

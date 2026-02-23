#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

MODE="${1:-check}"

if [[ "$MODE" == "fix" ]]; then
  echo "Running Ruff with auto-fix..."
  uv run ruff check --fix .
  uv run ruff format .
elif [[ "$MODE" == "check" ]]; then
  echo "Running Ruff checks..."
  uv run ruff check .
  uv run ruff format --check .
else
  echo "Usage: $0 [check|fix]"
  exit 2
fi

echo "Running MyPy..."
uv run mypy .

echo "Running tests..."
uv run pytest -q

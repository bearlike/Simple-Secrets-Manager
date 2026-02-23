#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

git config core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/pre-push scripts/quality.sh

echo "Installed repository hooks via core.hooksPath=.githooks"
echo "Active hooks:"
echo "  - pre-commit (ruff auto-fix + format)"
echo "  - pre-push (ruff fix + mypy + pytest)"

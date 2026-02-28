#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION_FILE="$REPO_ROOT/VERSION"

if [[ ! -f "$VERSION_FILE" ]]; then
  echo "Missing VERSION file at $VERSION_FILE"
  exit 1
fi

APP_VERSION="$(tr -d '[:space:]' <"$VERSION_FILE")"
if [[ -z "$APP_VERSION" ]]; then
  echo "VERSION file is empty"
  exit 1
fi

export APP_VERSION

cd "$REPO_ROOT"
echo "Deploying Docker stack with APP_VERSION=$APP_VERSION"
docker compose up -d --build

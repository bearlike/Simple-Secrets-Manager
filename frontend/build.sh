#!/usr/bin/env bash
set -euo pipefail

# Optional standalone frontend image build.
# Primary deployment path is the unified root image (see ../build.sh).

VERSION="${1:-0.0.1}"
IMAGE_NAME="${IMAGE_NAME:-ghcr.io/bearlike/ssm-admin-console}"

docker buildx create --platform linux/amd64,linux/arm64 --name ssm-frontend-builder 2>/dev/null || true
docker buildx build --no-cache --builder ssm-frontend-builder --push --platform linux/amd64,linux/arm64 \
  -t "${IMAGE_NAME}:latest" \
  -t "${IMAGE_NAME}:${VERSION}" \
  -f Dockerfile .

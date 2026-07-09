# syntax=docker/dockerfile:1.7
#
# Lean, self-contained image for the ssm-reload service. It depends only
# on the SSM public HTTP API and the local Docker socket -- it does NOT
# ship the SSM backend, Flask, or Mongo drivers. Build from the repo root:
#
#   docker build -f ssm_reload/Dockerfile -t ssm-reload .
#
FROM python:3.13-slim-bookworm

LABEL org.opencontainers.image.title="ssm-reload"
LABEL org.opencontainers.image.description="Recreate containers when their SSM config secrets change."
LABEL org.opencontainers.image.source="https://github.com/bearlike/simple-secrets-manager"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SSM_RELOAD_POLL_INTERVAL=30 \
    SSM_RELOAD_LABEL_PREFIX=ssm

WORKDIR /app

# Only the two runtime dependencies; keep the image small.
RUN pip install --no-cache-dir "requests>=2.32.3,<3.0.0" "docker>=7,<8"

COPY ssm_reload/ /app/ssm_reload/

# Runs as an unprivileged user; the mounted docker socket grants access.
RUN useradd --system --no-create-home ssm-reload
USER ssm-reload

ENTRYPOINT ["python", "-m", "ssm_reload"]

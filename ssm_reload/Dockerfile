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
    SSM_RELOAD_POLL_INTERVAL=30

WORKDIR /app

# Runtime deps: the SSM HTTP client + Docker SDK, plus pydantic +
# pydantic-settings for the shared typed contract (`ssm_contracts`) and the
# validated `ReloadSettings` config, and the OTel line for optional event
# export (mirrors the `reload` extra; emission stays off until
# OTEL_EXPORTER_OTLP_ENDPOINT is set).
RUN pip install --no-cache-dir \
    "requests>=2.32.3,<3.0.0" \
    "docker>=7,<8" \
    "pydantic>=2.5,<3.0" \
    "pydantic-settings>=2.0,<3.0" \
    "opentelemetry-api==1.43.0" \
    "opentelemetry-sdk==1.43.0" \
    "opentelemetry-semantic-conventions==0.64b0" \
    "opentelemetry-exporter-otlp-proto-http==1.43.0"

# Leaf packages the reloader imports. All three are copied so the image can
# construct the typed contract, emit events, and render projected env files
# (byte-identically to the CLI -- see ssm_projection).
COPY ssm_reload/ /app/ssm_reload/
COPY ssm_contracts/ /app/ssm_contracts/
COPY ssm_telemetry/ /app/ssm_telemetry/
COPY ssm_projection/ /app/ssm_projection/

# Runs as root, deliberately. Two reasons, and the first one is fatal without
# it: the projection volume is a root-owned tmpfs at mode 0750 (that mode is
# what keeps projected secrets private), so a non-root uid cannot write the
# dotenv files this service exists to render — it would fail on every config,
# forever. The second: this service's whole job needs the Docker socket, and
# anything that can reach the socket can start a privileged container, so it is
# root-equivalent on the host regardless of the uid inside the container. A
# non-root USER here bought no isolation; it only broke delivery.
ENTRYPOINT ["python", "-m", "ssm_reload"]

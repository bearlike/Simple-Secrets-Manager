# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM python:3.13-slim-bookworm AS backend-builder
COPY --from=ghcr.io/astral-sh/uv:0.9.29 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
# The unified image runs the Flask REST API, so it needs the `server` extra
# (flask-restx, pymongo, loguru, ...) on top of the lean base dependencies.
RUN uv sync --frozen --no-dev --no-install-project --extra server
COPY . .
RUN uv sync --frozen --no-dev --extra server

FROM python:3.13-slim-bookworm
ARG APP_VERSION=unknown
LABEL org.opencontainers.image.title="Simple Secrets Manager"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.authors="Krishnakanth Alagiri"
LABEL org.opencontainers.image.url="https://github.com/bearlike/simple-secrets-manager"
LABEL org.opencontainers.image.source="https://github.com/bearlike/simple-secrets-manager"
LABEL org.opencontainers.image.description="Simple Secrets Manager unified image with backend API and admin console."

ARG DEBIAN_FRONTEND=noninteractive
ARG NGINX_VERSION=1.22.*
ARG SUPERVISOR_VERSION=4.2.*
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nginx=${NGINX_VERSION} \
        supervisor=${SUPERVISOR_VERSION} \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=backend-builder /app /app
COPY --from=frontend-builder /frontend/dist /usr/share/nginx/html
COPY deploy/nginx.unified.conf /etc/nginx/conf.d/default.conf
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=5000
ENV BIND_HOST=0.0.0.0
ENV CONNECTION_STRING=mongodb://root:password@mongo:27017
ENV TOKEN_SALT=docker-local-dev
ENV CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,http://localhost:5000,http://127.0.0.1:5000

EXPOSE 8080 5000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

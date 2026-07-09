# ssm-reload

**Watchtower for secrets.** `ssm-reload` is a small, stateless service
that watches your Simple Secrets Manager configs and recreates any
opted-in Docker container with fresh environment whenever its secrets
change — no manual redeploys, no hand-edited `.env` files.

## How it works

Containers subscribe with two labels; `ssm-reload` manages the third:

```yaml
services:
  web:
    image: myorg/web-api:latest
    labels:
      ssm.enable: "true"       # opt in — nothing is touched without it
      ssm.config: "web/prod"   # which SSM project/config to track
      # ssm.revision is stamped by ssm-reload — do not set it yourself
```

The service polls the SSM API with cheap conditional requests (and
watches the local Docker event stream for instant adoption). When a
config's secrets change, every container bound to it is recreated with
the new values — safely: the original container is only removed after
its replacement is confirmed running.

## Run it

Already running the root stack? `docker-compose.yml` at the repo root ships
`ssm-reload` behind an opt-in `reload` Compose profile:

```bash
SSM_RELOAD_TOKEN=<a scoped service token> docker compose --profile reload up -d
```

Standalone:

```yaml
services:
  ssm-reload:
    image: ghcr.io/bearlike/ssm-reload:latest
    restart: unless-stopped
    environment:
      SSM_BASE_URL: "http://ssm:5000/api"
      SSM_TOKEN: "${SSM_RELOAD_TOKEN}"   # read-only, scoped service token
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

A complete, runnable example lives in
[`docker-compose.example.yml`](docker-compose.example.yml). Run one
instance per Docker host — it is stateless and manages only its local
daemon, so instances never conflict.

## Documentation

Full product guide — quick start, configuration reference, behavior,
and security notes: [`docs/SECRETS_RELOADER.md`](../docs/SECRETS_RELOADER.md)

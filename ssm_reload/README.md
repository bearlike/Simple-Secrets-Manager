# ssm-reload

**Watchtower for secrets.** `ssm-reload` is a small, stateless service that
keeps your workloads' secrets current: it renders every managed Simple Secrets
Manager config to a dotenv file your stack reads at deploy time, and recreates
the containers that have no other owner when those secrets change — no manual
redeploys, no hand-edited `.env` files.

## The one thing to understand

A container's environment is **frozen when it is created**. Only whoever creates
a container can decide what environment it gets. So `ssm-reload` does two
deliberately separate jobs:

1. **Delivery.** It writes each config to `/run/ssm/<project>-<config>.env` in a
   shared, RAM-backed Docker volume. Your stack points `env_file:` at that path,
   so every container is *born* with the right secrets — including on its very
   first boot, which post-hoc injection can never fix.
2. **Convergence.** When secrets change, it recreates the containers it is the
   only owner of. A container another tool created is **reported, not
   recreated** — you redeploy it, and it comes back born-correct.

The principle behind both: **SSM never takes a container away from its owner.**

## Use it

Give the reloader the volume, and point your services at it:

```yaml
volumes:
  ssm-env:
    external: true                    # created and owned by ssm-reload

services:
  gluetun:
    image: qmcgaw/gluetun
    env_file:
      - /run/ssm/vpn-zurich.env       # secrets, projected by SSM
    environment:                      # app-native config, stays in git
      VPN_SERVICE_PROVIDER: protonvpn
      VPN_TYPE: wireguard
    volumes:
      - ssm-env:/run/ssm:ro
    labels:
      com.bearlike.ssm.enable: "true"       # opt in — nothing touched without it
      com.bearlike.ssm.config: "vpn/zurich" # which SSM project/config to track
      # com.bearlike.ssm.revision and .keys are stamped by ssm-reload — don't set them
```

Compose **merges** `env_file` and `environment`, so app-native variables live
alongside the injected secrets rather than being replaced by them. And because
compose folds an `env_file`'s *contents* into its config hash, rewriting the
file and running `docker compose up -d` recreates exactly the affected services,
in dependency order — carrying any `network_mode: "service:X"` dependents along.

A complete, runnable example (including a netns-sharing dependent) lives in
[`docker-compose.example.yml`](docker-compose.example.yml).

### Bootstrap: the file must exist before the first `compose up`

Compose refuses to start a service whose `env_file` is missing, and on a first
deploy no container carries the label yet for the reloader to find. Two ways to
put the file there first:

- list the config in `SSM_RELOAD_PROJECTION_CONFIGS` (e.g. `vpn/zurich,web/prod`),
  so the reloader projects it whether or not anything is bound to it; or
- run `ssm secrets materialize --dir /run/ssm --project vpn --config zurich`
  yourself. The CLI renders byte-identical contents, so the two never fight.

`ssm secrets materialize --path /etc/gluetun.env` writes one exact file, which is
what systemd's `EnvironmentFile=` wants.

### Run it

Already running the root stack? `docker-compose.yml` at the repo root ships
`ssm-reload` behind an opt-in `reload` Compose profile:

```bash
SSM_RELOAD_TOKEN=<a scoped service token> docker compose --profile reload up -d
```

Run one instance per Docker host — it is stateless and manages only its local
daemon, so instances never conflict.

## What it will and won't touch

| Container | What happens when its secrets change |
| --- | --- |
| Created by SSM's own recreate, or by a plain `docker run` | Recreated with the fresh secrets **merged** over its existing environment. |
| Created by another tool (any `com.docker.compose.project` label — a compose stack, a Portainer stack, a Swarm service) | **Reported as divergent and left alone.** Its `env_file` is already up to date; redeploy it to pick the secrets up. |
| Created seconds ago, or created-but-not-yet-started | Left alone until it settles — a short window so a deploy in flight is never yanked out from under the tool performing it. |
| Donating its network namespace to another owner's container | Not recreated: a recreate mints a new container id and would strand them. Redeploy the stack instead. |

A recreate **merges** — it never replaces. Every variable your compose file set
survives; only the config's own keys are overwritten, and a key you *delete*
from a config is pruned from the container (tracked via the
`com.bearlike.ssm.keys` label).

## ⚠️ Migration: compose-owned containers are no longer recreated

If you already run `ssm-reload`, this is the behavior change to know about:

- **Before:** any labelled container was recreated when its secrets changed —
  including containers compose created. That raced compose's own deploys (it
  renamed a container aside mid-`compose up`, and the deploy died), and it
  **replaced the container's entire environment**, dropping every variable that
  came from the compose file but not from the SSM config.
- **Now:** a compose-owned container is reported as divergent and left alone. It
  shows as `error` in the reload fleet view with a message telling you to
  redeploy it.

**What you should do:** move those services onto the `env_file` pattern above.
Then a `docker compose up -d` is all it takes, and the container comes up with
correct secrets on its first boot instead of crash-looping until the reloader
catches it.

There is no setting to bring the old recreate-on-drift behavior back. It raced
your deploys and silently dropped compose-file-only variables — the kind of
failure that only surfaces once, in production, at the worst time.

## Documentation

Full product guide — quick start, configuration reference, behavior, and
security notes: [`docs/SECRETS_RELOADER.md`](../docs/SECRETS_RELOADER.md).
Every environment variable: [`docs/ENV_REFERENCE.md`](../docs/ENV_REFERENCE.md).

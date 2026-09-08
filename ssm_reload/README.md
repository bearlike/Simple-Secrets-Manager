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

## Swarm mode

The bind-mounted `ssm-env` volume above only works on a **single Docker
host**: a Swarm service's tasks can land on any node, and a plain Docker
volume does not follow them there. Set `SSM_RELOAD_SWARM_MODE=true` to switch
delivery to **Docker Swarm secrets or configs** instead — cluster-wide
objects Swarm itself replicates to whichever node a task runs on.

What's different from the default mode:

- **The unit of change is the *service*, not a container.** ssm-reload
  discovers Swarm services carrying `com.bearlike.ssm.enable=true` on
  EITHER a service label (`deploy.labels` in a stack file) or a container
  label (plain `labels:` under the service, without `deploy:`) — Compose
  puts those two in different places, so ssm-reload checks both rather than
  making you get the placement right. It mints a new immutable
  secret/config object per revision and calls `docker service update` to
  point the service at it. Swarm turns that into a rolling replacement of
  every task, on every node — **this does reload running workloads
  automatically**, the same promise as the default mode.
- **Secrets are delivered as a mounted FILE, never as literal service env.**
  Docker Swarm has no mechanism to merge secret bytes into a service's `Env`
  the way a recreated container's environment can be merged. A Swarm
  **secret**'s mount directory is fixed by Swarm itself — it always lands at
  `/run/secrets/<project>-<config>.env` — while a Swarm **config** has no such
  restriction, so it is mounted under `SSM_RELOAD_SWARM_CONFIG_MOUNT_DIR`
  instead (default `/run/ssm`, matching the non-swarm mode's path).
  **Your image's entrypoint must read that file itself** — source it
  (`. /run/secrets/web-prod.env`) before exec'ing the real process, or use
  an image that already reads `*_FILE`/dotenv-style secrets. An image that
  hard-requires literal env vars and cannot be given an entrypoint wrapper
  **cannot pick up a rotated secret automatically** in this mode; stay on the
  default (non-swarm) mode for it, or restart it by hand after a rotation.
- **Only a swarm MANAGER can create secrets/configs or update a service.**
  Point ssm-reload's Docker socket at a manager node, and run **exactly one
  instance for the whole swarm** — not one per node. Two instances would race
  each other minting differently-named objects for the same revision.
  `deploy.placement.constraints: [node.role == manager]` in the stack file is
  how you pin it there.
- **Old objects are pruned automatically, once nothing references them.**
  Docker refuses to delete a secret still bound to a task, so ssm-reload
  recomputes "is anything still using this?" from live cluster state every
  pass and removes what it minted once nothing does — it holds no durable
  bookkeeping of its own, same as everywhere else in this service.
- **`SSM_RELOAD_SWARM_SECRET_KIND`** picks `secret` (encrypted at rest — the
  default) or `config` (plain) as the object type.
- **`SSM_RELOAD_SWARM_CONFIG_MOUNT_DIR`** (default `/run/ssm`) picks where a
  `config`-kind object is mounted; ignored for the `secret` kind, whose
  directory Swarm itself fixes.
- **First boot is a real gap, not a nice-to-have.** A service's very first
  `docker stack deploy` starts before ssm-reload has ever seen it, so no
  secret is attached yet — an image that hard-requires the file will
  crash-loop until the next poll (`SSM_RELOAD_POLL_INTERVAL`) attaches it and
  rolls the service. Unlike the default mode's `SSM_RELOAD_PROJECTION_CONFIGS`
  bootstrap list, there is no way to pre-attach a secret to a service that
  does not exist yet — this is a structural property of Swarm secrets being
  service-scoped, not a missing feature. You CAN close this gap yourself:
  pre-create a placeholder secret and reference it statically in the
  service's own `secrets:` block, at the SAME target ssm-reload will use
  (`<project>-<config>.env`). ssm-reload's first successful pass replaces
  that reference with its own live one at the same target — matched by
  mount path, not by name — so the placeholder is taken over cleanly rather
  than left attached alongside it. See the bootstrap comment in
  `docker-stack.swarm.example.yml` for the exact commands.

A complete, runnable stack lives at
[`docker-stack.swarm.example.yml`](docker-stack.swarm.example.yml).

## Documentation

Full product guide — quick start, configuration reference, behavior, and
security notes: [`docs/SECRETS_RELOADER.md`](../docs/SECRETS_RELOADER.md).
Every environment variable: [`docs/ENV_REFERENCE.md`](../docs/ENV_REFERENCE.md).

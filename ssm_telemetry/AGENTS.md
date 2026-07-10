# ssm_telemetry — Agent Guide

> Nearest-scope guide for `ssm_telemetry/`. Read the [root `AGENTS.md`](../AGENTS.md)
> first for cross-cutting principles and the memory protocol. This file
> captures only what is **not obvious from the code** in this scope.
> `CLAUDE.md` here is a symlink to this file — edit this one.

## Responsibility

A tiny OpenTelemetry event emitter shared by the server and the reloader:
`configure(service_name, service_version)`, `emit_event(event_name, ...)`,
`instance_id()`, plus `is_active()`/`shutdown()` for lifecycle/tests.

## Non-obvious decisions

- **This is a LEAF.** It imports NO other project package (import-linter
  enforces `ssm_telemetry is a leaf`). Both server and reloader import it; it
  imports neither.
- **Logs API + first-class `event_name`, not the Events API.** Events go
  through `logger.emit(body=..., event_name=..., severity_number=...,
  attributes=...)` (opentelemetry-python 1.43.0). The `opentelemetry.sdk._events`
  Events API is deprecated (1.39.0) and the stdlib `LoggingHandler` bridge is
  deprecated (1.40.0) AND drops `event_name` — both avoided deliberately. The
  OTLP **HTTP** exporter is used on purpose; the umbrella
  `opentelemetry-exporter-otlp` drags in grpcio.
- **Zero-cost by default, and the endpoint is INJECTED — this leaf reads no
  env.** `configure(service_name, service_version, *, endpoint=None,
  exporter=None)` is a no-op — and the SDK/exporter are NEVER imported —
  unless an `endpoint` is passed (or an `exporter` is injected, which tests
  use for an in-memory exporter). The endpoint is passed by each service from
  its own settings object (`ServerSettings.otel_exporter_otlp_endpoint` /
  `ReloadSettings.otel_endpoint`); `ssm_telemetry` no longer reads
  `OTEL_EXPORTER_OTLP_ENDPOINT` itself, keeping the leaf free of the scattered
  config surface. The real OTLP/HTTP exporter still resolves its own signal URL
  from the standard `OTEL_EXPORTER_OTLP_*` vars (SDK convention), so `endpoint`
  is the activation gate, not the URL threaded through. A subprocess test pins
  "no endpoint ⇒ `opentelemetry.sdk` never imported".
- **Degrades without the `otel` extra.** Every `opentelemetry` import is
  guarded by `try/except ImportError`, so a CLI-only checkout (no `otel`
  extra) still imports `ssm_telemetry` and every call becomes a silent no-op.
- **Best-effort, never raises.** `emit_event` swallows and logs any error from
  the OTel path — telemetry must never break a reconcile pass or a request.
- **Severity constants (`INFO`/`WARN`/`ERROR`) are plain ints** (OTel
  `SeverityNumber` values) so the public signature never forces an
  `opentelemetry` import on callers.

## Session Lessons (Non-Trivial)

- Tests activate telemetry via an injected in-memory exporter; a
  `tests/telemetry/conftest.py` autouse fixture calls `shutdown()` after each
  test, because `configure()` wires a PROCESS-GLOBAL provider that would
  otherwise leak into unrelated tests (emit reads the same global).

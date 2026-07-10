"""OpenTelemetry-compatible structured events (leaf package).

A tiny wrapper over the OTel **Logs** API used to emit discrete events from
both the server and the reloader across the HTTP boundary. It imports no other
project package (enforced by import-linter) so either side may depend on it.

Design (verified against opentelemetry-python 1.43.0):

* Events go through the Logs API with the first-class ``event_name`` kwarg
  (``logger.emit(body=..., event_name=..., severity_number=..., ...)``), NOT
  the deprecated Events API or the stdlib ``LoggingHandler`` bridge (which
  drops ``event_name``).
* **Zero-cost by default.** :func:`emit_event` is a no-op — and the SDK /
  exporter are never imported — unless an ``endpoint`` is passed to
  :func:`configure` (or an ``exporter`` is injected for tests). The endpoint
  is injected by each service from its own settings object; this leaf reads
  no environment variable of its own. No endpoint, no cost.
* Every ``opentelemetry`` import is guarded, so the package degrades to a
  no-op when the ``otel`` extra is not installed (e.g. a CLI-only checkout).
"""

from __future__ import annotations

import logging
import socket
import uuid
from typing import Any, Mapping

__all__ = [
    "configure",
    "emit_event",
    "instance_id",
    "is_active",
    "shutdown",
    "INFO",
    "WARN",
    "ERROR",
]

__version__ = "0.1.0"

# OTel SeverityNumber values (logs data model) as plain ints, so the public
# signatures never force an opentelemetry import on callers.
INFO = 9
WARN = 13
ERROR = 17

_INSTRUMENTATION_NAME = "ssm_telemetry"

_log = logging.getLogger("ssm_telemetry")

# Populated by configure() only when telemetry is actually active. `Any` here
# is deliberate: the concrete SDK types are guarded behind optional imports.
_logger: Any = None
_provider: Any = None
_instance_id: str | None = None


def instance_id() -> str:
    """Return a stable, process-lifetime uuid4 (the ``service.instance.id``).

    Lazily generated on first use so importing the package costs nothing and
    every event/report from this process shares one identity.
    """
    global _instance_id
    if _instance_id is None:
        _instance_id = str(uuid.uuid4())
    return _instance_id


def configure(
    service_name: str,
    service_version: str | None = None,
    *,
    endpoint: str | None = None,
    exporter: Any = None,
) -> None:
    """Wire (or re-wire) event emission for this process.

    A no-op unless an ``endpoint`` (OTLP/HTTP) is passed or an ``exporter`` is
    injected (tests use an in-memory exporter). Each service passes the
    endpoint from its own settings object — this leaf never reads the
    environment. The no-endpoint path never imports the SDK or an exporter —
    that is the zero-cost contract. Safe to call once at start-up; a missing
    ``otel`` extra degrades to a no-op.
    """
    if exporter is None and not endpoint:
        _shutdown_provider()
        return
    try:
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import (
            BatchLogRecordProcessor,
            SimpleLogRecordProcessor,
        )
        from opentelemetry.sdk.resources import Resource
    except ImportError:
        # The `otel` extra is not installed; stay a silent no-op.
        return

    attributes: dict[str, Any] = {
        "service.name": service_name,
        "service.instance.id": instance_id(),
        "host.name": socket.gethostname(),
    }
    if service_version:
        attributes["service.version"] = service_version
    provider = LoggerProvider(resource=Resource.create(attributes))

    if exporter is not None:
        # Injected (tests): SimpleLogRecordProcessor exports synchronously on
        # emit, so assertions need no flush and stay deterministic.
        provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    else:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import (
            OTLPLogExporter,
        )

        # The injected ``endpoint`` gates activation (above); the OTLP/HTTP
        # exporter resolves its own signal URL from the standard
        # OTEL_EXPORTER_OTLP_* variables (appending ``/v1/logs`` to the base),
        # which is the conventional OTLP config path — so no URL is threaded
        # through here.
        provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter())
        )

    _shutdown_provider()
    _set_provider(provider)


def emit_event(
    event_name: str,
    body: Any = None,
    severity: int = INFO,
    attributes: Mapping[str, Any] | None = None,
) -> None:
    """Emit one discrete event; a no-op until :func:`configure` activates.

    Best-effort by contract: any failure inside the OTel path is logged and
    swallowed, never raised into the caller's control flow.
    """
    logger = _logger
    if logger is None:
        return
    try:
        from opentelemetry._logs import SeverityNumber

        logger.emit(
            body=body,
            event_name=event_name,
            severity_number=SeverityNumber(severity),
            attributes=dict(attributes) if attributes else None,
        )
    except Exception as exc:  # telemetry must never break the caller.
        _log.warning("telemetry emit failed for %s: %s", event_name, exc)


def is_active() -> bool:
    """Whether an exporter is currently wired (telemetry is emitting)."""
    return _logger is not None


def shutdown() -> None:
    """Flush and tear down the provider, reverting to the no-op state."""
    _shutdown_provider()


def _set_provider(provider: Any) -> None:
    global _logger, _provider
    _provider = provider
    _logger = provider.get_logger(_INSTRUMENTATION_NAME, __version__)


def _shutdown_provider() -> None:
    global _logger, _provider
    provider = _provider
    _provider = None
    _logger = None
    if provider is not None:
        try:
            provider.shutdown()
        except Exception as exc:  # best-effort teardown.
            _log.warning("telemetry shutdown failed: %s", exc)

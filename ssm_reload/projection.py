"""Delivery: keep every managed config rendered to its projection sink.

This is the layer that makes the rest of the design possible. A container's
environment is frozen at *create* time, so the reloader can never make a
container be BORN with the right secrets -- only its creator can. Projection
puts the secrets where that creator already looks: a dotenv file it names
with ``env_file:`` (compose), ``EnvironmentFile=`` (systemd), or reads
directly (an image with ``*_SECRETFILE`` support).

The consequence is the whole point: once a workload is born correct, the
reloader's steady state is *adopt*, not *recreate*.

:class:`Projector` is the reloader's stateful wrapper over the stateless
:class:`~ssm_projection.ProjectionSink`: it knows which configs are already
rendered (so a missing file forces a re-render even in the 304 steady state)
and remembers the revision it last rendered (so a config with no container
bound to it still gets the cheap ``If-None-Match`` fast path). Rendering is a
best-effort side effect: a broken sink is logged, reported, and never breaks a
pass.
"""

from __future__ import annotations

import logging

import ssm_telemetry
from ssm_projection import ProjectionSink
from ssm_reload.models import ConfigRef

logger = logging.getLogger("ssm_reload.projection")


class Projector:
    """Renders configs to a sink, and remembers what it has rendered."""

    def __init__(self, sink: ProjectionSink) -> None:
        self.sink = sink
        # Revision last rendered per config. Process-local, like the
        # AdoptionCache: the no-durable-state doctrine holds, and a restart
        # merely costs one unconditional export per config.
        self._revisions: dict[ConfigRef, str] = {}

    def needs_render(self, ref: ConfigRef) -> bool:
        """True when this config has no file in the sink.

        The projection volume is RAM-backed, so it is EMPTY after a reboot (or
        once the last container holding it exits) while the containers still
        carry their revision label. A conditional export would return 304 and
        the file would never come back -- so a missing file forces an
        unconditional export.
        """
        try:
            return not self.sink.exists(ref.project, ref.config)
        except OSError as exc:
            # "Cannot tell" must mean "render it": assuming the file is there
            # would leave a broken sink un-rendered AND un-exported forever.
            logger.warning(
                "Cannot inspect the projection sink for %s: %s", ref, exc
            )
            return True

    def last_revision(self, ref: ConfigRef) -> str | None:
        """The revision last rendered for a config with no container bound."""
        return self._revisions.get(ref)

    def render(
        self, ref: ConfigRef, secrets: dict[str, str], revision: str
    ) -> str | None:
        """Write ``secrets`` to the sink; return an error message, or None.

        Best-effort by contract: a read-only mount or an unrenderable key must
        not stop the reloader from converging the containers that still need a
        recreate, so a failure never raises. It is RETURNED rather than merely
        logged, because delivery is now the primary path: a config nothing is
        bound to yet has no container outcome to go red, and reporting it
        "current" while no env_file was ever written would leave an operator
        staring at a green fleet view and a stack that will not start.
        """
        try:
            target = self.sink.write(ref.project, ref.config, secrets)
        except (OSError, ValueError) as exc:
            message = f"could not project {ref}: {exc}"
            logger.warning("%s", message)
            ssm_telemetry.emit_event(
                "ssm_reload.projection.failed",
                severity=ssm_telemetry.ERROR,
                attributes={
                    "ssm.project": ref.project,
                    "ssm.config": ref.config,
                    "error": str(exc),
                },
            )
            return message

        self._revisions[ref] = revision
        logger.info(
            "Projected %s (%d keys) to %s at %s",
            ref,
            len(secrets),
            target,
            revision,
        )
        ssm_telemetry.emit_event(
            "ssm_reload.projection.written",
            attributes={
                "ssm.project": ref.project,
                "ssm.config": ref.config,
                "ssm.revision.to": revision,
                "ssm.target": target,
            },
        )
        return None

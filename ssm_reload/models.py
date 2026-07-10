"""Driver-agnostic data carried across the seam.

A :class:`ConfigRef` is an SSM ``project/config`` coordinate. A :class:`Unit`
is one managed workload (a Docker container in v1). A :class:`Binding` is what
a unit's labels say it should track: a coordinate plus the revision (ETag) it
currently holds. A :class:`Lifecycle` is what the runtime knows about who ELSE
has a claim on that workload -- the facts that decide whether SSM may recreate
it at all.

Each class owns the questions about its own state: `Lifecycle` answers "may I
touch this?", not the reconcile loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ssm_contracts import is_valid_slug
from ssm_reload.errors import BindingError


@dataclass(frozen=True)
class ConfigRef:
    """An SSM ``project/config`` coordinate.

    The single parser for that string shape. Both places it arrives from the
    outside world -- a container's ``<prefix>.config`` label and the
    ``SSM_RELOAD_PROJECTION_CONFIGS`` setting -- go through :meth:`parse`, so a
    non-slug is rejected at the boundary rather than surviving into a report,
    where it would fail pydantic validation and abort a whole reconcile pass.
    """

    project: str
    config: str

    @classmethod
    def parse(cls, value: str) -> "ConfigRef":
        """Parse ``"project/config"``; raise :class:`BindingError` if it isn't.

        Raises:
            BindingError: either half is missing or is not a lowercase slug.
        """
        project, separator, config = value.partition("/")
        if (
            not separator
            or not is_valid_slug(project)
            or not is_valid_slug(config)
        ):
            raise BindingError(
                f"{value!r} must be 'project/config' with lowercase slugs "
                "(matching ^[a-z0-9_-]+$)"
            )
        return cls(project=project, config=config)

    def __str__(self) -> str:
        return f"{self.project}/{self.config}"


@dataclass(frozen=True)
class Dependent:
    """A workload living inside another unit's network namespace.

    Compose's ``network_mode: "service:gluetun"`` is stored as
    ``NetworkMode: container:<id>``. Recreating the donor mints a new id, so
    every dependent is left attached to a namespace that no longer exists.
    ``owner`` is that dependent's own external lifecycle owner, if any --
    SSM may carry an unowned passenger across to the new namespace, but it
    may not touch one that belongs to somebody else.
    """

    id: str
    name: str
    owner: str | None = None


@dataclass(frozen=True)
class Lifecycle:
    """Who else owns a unit, and whether it is settled enough to touch.

    Defaults describe the simple case the reloader was built for: a
    long-running container nobody else manages. Every field is a REASON TO
    REFUSE a recreate, so a driver that cannot determine one leaves it at
    the permissive default rather than guessing, and the questions the
    reconcile loop asks about those reasons are answered HERE -- the state and
    the rules over it belong together.
    """

    # An external lifecycle owner (a compose project name). Set => SSM did
    # not create this container and must not recreate it.
    owner: str | None = None
    # The runtime's own status string ("running", "created", "exited", ...).
    # "created" means another tool has made it but not started it yet: a
    # deploy is in flight.
    status: str = "running"
    # Seconds since the container was created; None when unknown.
    age_seconds: float | None = None
    dependents: tuple[Dependent, ...] = ()

    def settling_reason(self, window_seconds: float) -> str | None:
        """Why this unit is still mid-deploy, or None once it has settled.

        Recreating a container another tool is still converging destroys that
        tool's deploy, so a container that has not started yet, or that was
        created moments ago, is left alone until the window passes.
        """
        if self.status == "created":
            return (
                "created but not started yet: a deploy is in flight, "
                "leaving it alone"
            )
        if self.age_seconds is not None and self.age_seconds < window_seconds:
            return (
                f"created {self.age_seconds:.0f}s ago (settling window is "
                f"{window_seconds:.0f}s): a deploy may still be in flight, "
                "leaving it alone"
            )
        return None

    def stranded_by_recreate(self) -> tuple[str, ...]:
        """Names of dependents a recreate would strand, in sorted order.

        A recreate mints a new container id, so anything living in this unit's
        network namespace is left attached to one that no longer exists. SSM
        may carry an unowned passenger across; one that belongs to somebody
        else it may not touch at all, so the recreate must not happen.
        """
        return tuple(
            sorted(
                dependent.name
                for dependent in self.dependents
                if dependent.owner
            )
        )


@dataclass
class Unit:
    """One managed workload as seen by a driver.

    ``raw`` is the driver's own handle (e.g. a docker-py ``Container``);
    only the driver that produced a unit ever interprets it.
    """

    id: str
    name: str
    raw: Any = None
    lifecycle: Lifecycle = field(default_factory=Lifecycle)


@dataclass(frozen=True)
class Binding:
    """The SSM coordinates a unit tracks, plus its held revision."""

    project: str
    config: str
    held_revision: str | None

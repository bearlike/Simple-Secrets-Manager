"""The ``ReloadDriver`` seam.

The reconcile loop is platform-agnostic: it speaks only to this
interface. Docker is the only implementation in v1, but a Kubernetes
driver can be dropped in later without touching the client or the loop.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ssm_reload.models import Binding, Unit


@runtime_checkable
class ReloadDriver(Protocol):
    """A runtime that can discover, read, and recreate managed units."""

    def discover(self) -> list[Unit]:
        """Return every unit opted in to ssm-reload management."""
        ...

    def read_binding(self, unit: Unit) -> Binding:
        """Parse a unit's binding labels.

        Raises :class:`ssm_reload.errors.BindingError` when the binding
        labels are missing or malformed.
        """
        ...

    def apply(self, unit: Unit, env: dict[str, str], revision: str) -> None:
        """Recreate ``unit`` with ``env`` and stamp ``revision``.

        Preserves the unit's full runtime spec, replacing only its
        environment and recording ``revision`` as the new held value.
        """
        ...

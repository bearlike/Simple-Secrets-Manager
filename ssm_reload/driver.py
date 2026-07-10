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
        """Return every unit opted in to ssm-reload management.

        Each unit carries the :class:`~ssm_reload.models.Lifecycle` facts
        the loop needs to decide whether it may touch it at all: who else
        owns it, whether it has finished being deployed, and what is living
        inside its network namespace.
        """
        ...

    def read_binding(self, unit: Unit) -> Binding:
        """Parse a unit's binding labels.

        Raises :class:`ssm_reload.errors.BindingError` when the binding
        labels are missing or malformed.
        """
        ...

    def read_env(self, unit: Unit) -> dict[str, str]:
        """Return the unit's ACTUAL environment as a mapping.

        The adoption-by-comparison path judges an externally-recreated
        unit (revision label stripped) by its observed env rather than
        blind-recreating. Raises
        :class:`ssm_reload.errors.DriverError` when the environment
        cannot be read.
        """
        ...

    def read_managed_keys(self, unit: Unit) -> set[str]:
        """Return the key names SSM injected into ``unit`` last time.

        Empty for a unit SSM has never recreated. This is what tells a key
        SSM put there apart from one the app has always had -- without it, a
        key DELETED from a config could never be detected in a running
        container's environment, and adoption would keep a stale secret
        alive forever.
        """
        ...

    def apply(self, unit: Unit, env: dict[str, str], revision: str) -> None:
        """Recreate ``unit`` with ``env`` and stamp ``revision``.

        Preserves the unit's full runtime spec and MERGES ``env`` over its
        existing environment (replacing it would drop every app-native
        variable the unit's creator set), recording ``revision`` as the new
        held value. Anything sharing the unit's network namespace is carried
        across to the new one.
        """
        ...

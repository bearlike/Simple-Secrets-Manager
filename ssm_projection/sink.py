"""Where a rendered config lands.

The renderer is one code path; the destination is pluggable. Today there is
exactly one implementation, :class:`DirectorySink` — but it covers both
deployment shapes in the design, because what makes a directory a
RAM-backed Docker volume or a host path is a *mount-time* decision, not a
code one:

* the reloader mounts an SSM-owned tmpfs volume at its projection directory,
  and every consumer mounts that same volume read-only;
* an operator running the CLI on the host points ``--dir`` at a plain path
  for systemd's ``EnvironmentFile=`` or a host-side ``docker compose``,
  which cannot read a named volume (its backing path lives inside the
  daemon's storage).

:class:`ProjectionSink` is the seam a future non-filesystem target (a
Kubernetes Secret) implements without the renderer knowing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol, runtime_checkable

from ssm_projection.dotenv import render_dotenv
from ssm_projection.fsio import atomic_write_text

# Owner-write, group-read. The consuming container reads the file as a group
# member; nothing else on the host can. World-readable secrets would undo the
# point of a private tmpfs volume.
PROJECTION_FILE_MODE = 0o640


def env_filename(project: str, config: str) -> str:
    """The dotenv file name for one ``project/config`` pair."""
    return f"{project}-{config}.env"


@runtime_checkable
class ProjectionSink(Protocol):
    """A destination a rendered config can be delivered to."""

    def write(
        self, project: str, config: str, secrets: Mapping[str, str]
    ) -> str:
        """Deliver ``secrets``; return a human-readable target description."""
        ...

    def exists(self, project: str, config: str) -> bool:
        """True when this config has already been delivered here."""
        ...


class DirectorySink:
    """Writes ``<project>-<config>.env`` into one directory, atomically."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def path_for(self, project: str, config: str) -> Path:
        return self.directory / env_filename(project, config)

    def write(
        self, project: str, config: str, secrets: Mapping[str, str]
    ) -> str:
        target = self.path_for(project, config)
        # Atomic: a compose client reading this file mid-write must see the
        # whole previous version or the whole new one, never a half-file
        # (which it would parse as a truncated set of secrets).
        atomic_write_text(
            target, render_dotenv(secrets), mode=PROJECTION_FILE_MODE
        )
        return str(target)

    def exists(self, project: str, config: str) -> bool:
        return self.path_for(project, config).is_file()

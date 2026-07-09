"""Driver-agnostic data carried across the seam.

A :class:`Unit` is one managed workload (a Docker container in v1). A
:class:`Binding` is what its labels say it should track: an SSM
``project/config`` plus the revision (ETag) it currently holds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Unit:
    """One managed workload as seen by a driver.

    ``raw`` is the driver's own handle (e.g. a docker-py ``Container``);
    only the driver that produced a unit ever interprets it.
    """

    id: str
    name: str
    raw: Any = None


@dataclass(frozen=True)
class Binding:
    """The SSM coordinates a unit tracks, plus its held revision."""

    project: str
    config: str
    held_revision: str | None

"""Render a project/config's secrets to a dotenv file in a pluggable sink.

The delivery half of SSM: a container's environment is frozen at *create*
time, so the only way a workload can be BORN with the right secrets is for
its creator (compose, systemd, a plain ``docker run``) to read them from a
file the creator already knows how to read. This package renders that file.

It is a LEAF — it imports no other SSM package, and both ``ssm_cli`` (the
``ssm secrets materialize`` bootstrap) and ``ssm_reload`` (the continuous
projection loop) depend on it. That is deliberate: the two MUST emit
byte-identical files, because ``docker compose`` folds an ``env_file``'s
CONTENTS into its config hash. Two renderers that disagreed on so much as
key order would make every ``compose up`` recreate services the reloader had
just settled, and vice versa.
"""

from ssm_projection.dotenv import render_dotenv
from ssm_projection.fsio import atomic_write_text
from ssm_projection.sink import (
    PROJECTION_FILE_MODE,
    DirectorySink,
    ProjectionSink,
    env_filename,
)

__all__ = [
    "PROJECTION_FILE_MODE",
    "DirectorySink",
    "ProjectionSink",
    "atomic_write_text",
    "env_filename",
    "render_dotenv",
]

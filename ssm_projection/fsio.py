"""Filesystem writes that are safe under concurrent processes.

Multiple writers routinely touch the same file at once: parallel `ssm` runs
share a cache/config/credentials file, and the reloader rewrites a projected
`.env` while a compose client may be reading it. A naive "write temp then
rename" is only safe if each writer uses its OWN temp file — deriving the
temp name from the target path makes every writer collide on one temp file,
corrupting it and crashing the loser at chmod/rename (this really happened;
see `ssm_cli/AGENTS.md`). This module centralises the correct pattern so
every caller gets it right.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, *, mode: int = 0o600) -> None:
    """Atomically write ``text`` to ``path``.

    A uniquely-named temp file is created in the target directory, fully
    written, fsynced, chmod-ed and then atomically renamed into place with
    :func:`os.replace`. Because each call gets its own temp file, any
    number of concurrent processes can write the same path without
    colliding, and a reader always observes either the old or the new
    complete file -- never a half-written one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        # Never leave our own temp file behind on failure.
        try:
            tmp.unlink()
        except OSError:
            pass
        raise

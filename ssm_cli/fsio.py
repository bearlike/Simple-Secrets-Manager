"""The CLI's atomic-write seam.

Kept as a named module because every local JSON writer in this package
(`cache.py`, `config.py`) routes through it, but the implementation now
lives in the `ssm_projection` leaf: the reloader needs the identical
write-temp-fsync-chmod-rename dance for projected `.env` files, and one
implementation of that dance is the only way it stays correct in both.
"""

from __future__ import annotations

from ssm_projection import atomic_write_text

__all__ = ["atomic_write_text"]

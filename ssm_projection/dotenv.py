"""The dotenv renderer — one definition, shared by the CLI and the reloader.

Every value is emitted double-quoted with ``\\``, ``"``, ``$``, newline and
carriage return escaped. That exact form was verified against a live
``docker compose`` client (Compose v5.3.1 / Docker 29.6.1): each value
round-trips byte-for-byte into the container's environment, including
values holding spaces, ``#``, ``=``, quotes and multi-line PEM bodies.

WHY quote at all, when the naive ``KEY=value`` form usually works: compose
parses an ``env_file`` with a dotenv parser that EXPANDS ``$VAR`` in an
unquoted value. A password containing ``$`` would be silently replaced with
whatever the compose client has in its own environment — usually nothing —
and the workload would come up with a corrupted secret and no error. The
escape is the difference between a secret and a footgun.
"""

from __future__ import annotations

import re
from typing import Mapping

# POSIX-portable environment variable names. Docker itself is laxer, but a
# dotenv parser is not: a key outside this shape produces a file compose
# cannot read, which fails the whole stack rather than one variable.
ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_ESCAPES = (
    ("\\", "\\\\"),  # first: later rules must not re-escape this backslash
    ('"', '\\"'),
    ("$", "\\$"),
    ("\n", "\\n"),
    ("\r", "\\r"),
)


def render_dotenv(secrets: Mapping[str, str]) -> str:
    """Render ``secrets`` as a dotenv document, sorted and escaped.

    Keys are sorted so the output is a pure function of the secret map:
    compose hashes an ``env_file``'s contents, so a reshuffled render would
    recreate every consuming service for no reason.

    Raises:
        ValueError: a key is not a usable environment variable name.
    """
    lines = []
    for key in sorted(secrets):
        if not ENV_KEY_PATTERN.match(key):
            raise ValueError(
                f"{key!r} is not a valid environment variable name "
                "(expected ^[A-Za-z_][A-Za-z0-9_]*$)"
            )
        lines.append(f'{key}="{_escape(secrets[key])}"')
    return "".join(f"{line}\n" for line in lines)


def _escape(value: str) -> str:
    for raw, escaped in _ESCAPES:
        value = value.replace(raw, escaped)
    return value

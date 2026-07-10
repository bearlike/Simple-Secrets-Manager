"""The dotenv renderer's quoting contract.

Every expectation here was verified against a live ``docker compose`` client
(Compose v5.3.1 / Docker 29.6.1): an ``env_file`` written this way round-trips
each value byte-for-byte into the container's environment. Compose parses the
file with a dotenv parser that (a) strips the surrounding double quotes,
(b) processes ``\\`` escapes, and (c) expands ``$VAR`` unless it is escaped —
so a renderer that does not escape ``$`` silently corrupts any secret
containing one.
"""

from __future__ import annotations

import pytest

from ssm_projection import render_dotenv


def _parsed(text: str) -> dict[str, str]:
    """Parse rendered output the way compose's dotenv parser does."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        key, _, raw = line.partition("=")
        assert raw.startswith('"') and raw.endswith('"'), raw
        body = raw[1:-1]
        value: list[str] = []
        escaped = False
        for char in body:
            if escaped:
                value.append({"n": "\n", "r": "\r"}.get(char, char))
                escaped = False
            elif char == "\\":
                escaped = True
            else:
                value.append(char)
        out[key] = "".join(value)
    return out


def test_values_round_trip_through_the_dotenv_escaping_rules() -> None:
    secrets = {
        "PLAIN": "abc123",
        "SPACES": "hello world",
        "HASH": "pa#ss",
        "DOLLAR": "pa$$w0rd",
        "BRACE": "${NOT_INTERPOLATED}",
        "DQUOTE": 'he"llo',
        "SQUOTE": "he'llo",
        "EQUALS": "a=b=c",
        "EMPTY": "",
        "BACKSLASH": "a\\nb",
        "PADDED": "  x  ",
        "WIREGUARD_PRIVATE_KEY": "cHJpdmF0ZQ==+/",
        "PEM": "-----BEGIN-----\nbody\n-----END-----",
    }

    assert _parsed(render_dotenv(secrets)) == secrets


def test_dollar_is_escaped_so_compose_never_interpolates_a_secret() -> None:
    # The single most dangerous case: an unescaped `$` makes compose expand
    # the value against its own environment, replacing the secret with "".
    assert render_dotenv({"K": "a${B}c"}) == 'K="a\\${B}c"\n'


def test_newlines_are_escaped_onto_one_line() -> None:
    # A multi-line secret (a PEM key) must not become multiple dotenv lines.
    rendered = render_dotenv({"K": "one\ntwo"})

    assert rendered == 'K="one\\ntwo"\n'
    assert len(rendered.splitlines()) == 1


def test_output_is_deterministic_and_key_sorted() -> None:
    # Compose folds env_file CONTENTS into its config hash, so a reshuffled
    # render would recreate every consuming service for no reason.
    first = render_dotenv({"B": "2", "A": "1"})

    assert first == 'A="1"\nB="2"\n'
    assert first == render_dotenv({"A": "1", "B": "2"})


def test_invalid_key_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="not a valid environment variable"):
        render_dotenv({"not-an-env-var": "x"})

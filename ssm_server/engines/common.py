#!/usr/bin/env python3
"""Common validation helpers shared across engines/resources."""

import re

SLUG_PATTERN = re.compile(r"^[a-z0-9_-]+$")
ENV_KEY_PATTERN = re.compile(r"^[A-Z0-9_]+$")

# Canonical ``${...}`` secret-reference token grammar. Single source of truth
# for both consumers: the engine-side scan in ``secrets_v2.py`` (the config
# delete guard's inbound-reference check) and the API-side resolver in
# ``api/resources/secrets/references.py``. It lives here — a leaf engines
# module both can import — so the pattern is defined once (api imports
# engines; engines never import api).
REFERENCE_TOKEN_PATTERN = re.compile(r"\$\{([^{}]+)\}")


def is_valid_slug(value: str) -> bool:
    return bool(value and SLUG_PATTERN.fullmatch(value))


def is_valid_env_key(value: str) -> bool:
    return bool(value and ENV_KEY_PATTERN.fullmatch(value))

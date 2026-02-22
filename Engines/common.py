#!/usr/bin/env python3
"""Common validation helpers shared across engines/resources."""
import re

SLUG_PATTERN = re.compile(r"^[a-z0-9_-]+$")
ENV_KEY_PATTERN = re.compile(r"^[A-Z0-9_]+$")


def is_valid_slug(value: str) -> bool:
    return bool(value and SLUG_PATTERN.fullmatch(value))


def is_valid_env_key(value: str) -> bool:
    return bool(value and ENV_KEY_PATTERN.fullmatch(value))

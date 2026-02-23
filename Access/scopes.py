#!/usr/bin/env python3
"""Shared scope defaults."""

DEFAULT_TOKEN_ACTION_SCOPES = [
    "projects:read",
    "projects:write",
    "configs:read",
    "configs:write",
    "secrets:read",
    "secrets:write",
    "secrets:export",
    "tokens:manage",
    "audit:read",
    "users:manage",
]


def global_scopes(actions=None):
    """Return global scopes payload for token documents."""
    return [{"actions": list(actions or DEFAULT_TOKEN_ACTION_SCOPES)}]

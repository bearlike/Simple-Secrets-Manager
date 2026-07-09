"""Shared pytest fixtures and environment hardening.

The CLI's auth layer talks to the OS keyring (``ssm_cli.auth.keyring``).
On a developer workstation the default SecretService/D-Bus backend can
block indefinitely (locked keyring, no D-Bus session), which would hang
the whole test run. CI is headless and never hits this, so the hang only
shows up locally. We force keyring off for the test session so every test
exercises the deterministic file-based credential path.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_keyring(monkeypatch):
    monkeypatch.setattr("ssm_cli.auth.keyring", None, raising=False)

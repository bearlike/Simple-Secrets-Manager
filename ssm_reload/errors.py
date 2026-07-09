"""Typed errors for ssm-reload.

The decision loop treats any :class:`SsmReloadError` raised while talking
to the SSM API as a signal to *do nothing* for that config -- it must
never tear down a healthy container because of a transient failure.
"""

from __future__ import annotations


class SsmReloadError(Exception):
    """Base class for every ssm-reload failure."""


class SsmClientError(SsmReloadError):
    """A call to the SSM HTTP API failed.

    ``status_code`` is the HTTP status when one was received, or ``None``
    for transport-level failures (DNS, connection, timeout). The loop
    catches this and skips the affected config without mutating any
    container. A ``403`` means the token cannot authorize the project;
    the loop logs and skips it -- it never "fails open".
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BindingError(SsmReloadError):
    """A managed unit's binding labels are missing or malformed."""


class DriverError(SsmReloadError):
    """The runtime driver failed to apply a change to a unit."""

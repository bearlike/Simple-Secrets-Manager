"""Fakes shared by the ssm-reload unit tests.

Everything here is hermetic: no live Docker daemon, no Mongo, no
network. The SSM client and the Docker SDK are both faked.
"""

from __future__ import annotations

from typing import Any

import pytest

from ssm_reload.models import Binding, Unit


class FakeSsmClient:
    """Records reconcile interactions and replays scripted exports."""

    def __init__(
        self, exports: dict[tuple[str, str], Any] | None = None
    ) -> None:
        # Map (project, config) -> either a result tuple or an Exception.
        self.exports = exports or {}
        self.export_calls: list[tuple[str, str, str | None]] = []
        self.reports: list[dict[str, Any]] = []

    def conditional_export(
        self, project: str, config: str, etag: str | None
    ) -> tuple[bool, dict[str, str] | None, str | None]:
        self.export_calls.append((project, config, etag))
        outcome = self.exports[(project, config)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def report_reload(self, payload: dict[str, Any]) -> None:
        self.reports.append(payload)


class FakeDriver:
    """Driver backed by in-memory units and bindings."""

    def __init__(
        self,
        units: list[Unit],
        bindings: dict[str, Binding | Exception],
        apply_error: Exception | None = None,
    ) -> None:
        self._units = units
        self._bindings = bindings
        self._apply_error = apply_error
        self.applied: list[tuple[str, dict[str, str], str]] = []

    def discover(self) -> list[Unit]:
        return list(self._units)

    def read_binding(self, unit: Unit) -> Binding:
        result = self._bindings[unit.id]
        if isinstance(result, Exception):
            raise result
        return result

    def apply(self, unit: Unit, env: dict[str, str], revision: str) -> None:
        # Record the attempt first so a test can assert apply was tried
        # even when it then fails (and therefore must NOT be reported).
        self.applied.append((unit.id, env, revision))
        if self._apply_error is not None:
            raise self._apply_error


@pytest.fixture
def make_unit():
    def _make(unit_id: str, name: str | None = None) -> Unit:
        return Unit(id=unit_id, name=name or unit_id, raw=None)

    return _make

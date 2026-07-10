"""Fakes shared by the ssm-reload unit tests.

Everything here is hermetic: no live Docker daemon, no Mongo, no
network. The SSM client and the Docker SDK are both faked.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, cast

import pytest

from ssm_contracts import Trigger
from ssm_reload.client import SsmClient
from ssm_reload.models import Binding, ConfigRef, Unit
from ssm_reload.projection import Projector
from ssm_reload.reconcile import AdoptionCache, Reconciler

HOST = "host-1"

# The configs the suite's fakes are bound to, marked as ALREADY projected:
# that is the steady state. An unprojected config correctly forces an
# unconditional export, which `test_reconcile.py` pins on its own.
PROJECTED = ("proj/prod", "proj/stage", "web/prod", "vpn/zurich")


class FakeSsmClient:
    """Records reconcile interactions and replays scripted exports."""

    def __init__(
        self,
        exports: dict[tuple[str, str], Any] | None = None,
        status_error: Exception | None = None,
    ) -> None:
        # Map (project, config) -> either a result tuple or an Exception.
        self.exports = exports or {}
        self.export_calls: list[tuple[str, str, str | None]] = []
        self.reports: list[dict[str, Any]] = []
        # Per-cycle status heartbeats (POST /reload/report); `status_error`
        # lets a test assert reconcile survives a failed status POST.
        self.status_reports: list[dict[str, Any]] = []
        self._status_error = status_error

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

    def report_status(self, payload: dict[str, Any]) -> None:
        # Record the attempt before optionally failing, so a test can assert
        # the report was built even when the POST then raises.
        self.status_reports.append(payload)
        if self._status_error is not None:
            raise self._status_error


class FakeDriver:
    """Driver backed by in-memory units and bindings."""

    def __init__(
        self,
        units: list[Unit],
        bindings: dict[str, Binding | Exception],
        apply_error: Exception | None = None,
        fail_ids: set[str] | None = None,
        envs: dict[str, dict[str, str] | Exception] | None = None,
        managed_keys: dict[str, set[str]] | None = None,
    ) -> None:
        self._units = units
        self._bindings = bindings
        self._apply_error = apply_error
        # When given, only these unit ids fail `apply`; otherwise every apply
        # fails when `apply_error` is set (the original behavior).
        self._fail_ids = fail_ids
        # Scripted actual container env per unit id (or an Exception to
        # raise), for the adoption-by-comparison path. Units without an
        # entry read as empty env, which never matches a non-empty export.
        self._envs = envs or {}
        # Key names a previous recreate stamped on the container (the
        # `com.bearlike.ssm.keys` label) -- what makes a REMOVED key
        # detectable rather than invisible.
        self._managed_keys = managed_keys or {}
        self.applied: list[tuple[str, dict[str, str], str]] = []

    def discover(self) -> list[Unit]:
        return list(self._units)

    def read_binding(self, unit: Unit) -> Binding:
        result = self._bindings[unit.id]
        if isinstance(result, Exception):
            raise result
        return result

    def read_env(self, unit: Unit) -> dict[str, str]:
        result = self._envs.get(unit.id, {})
        if isinstance(result, Exception):
            raise result
        return dict(result)

    def read_managed_keys(self, unit: Unit) -> set[str]:
        return set(self._managed_keys.get(unit.id, set()))

    def apply(self, unit: Unit, env: dict[str, str], revision: str) -> None:
        # Record the attempt first so a test can assert apply was tried
        # even when it then fails (and therefore must NOT be reported).
        self.applied.append((unit.id, env, revision))
        if self._apply_error is not None and (
            self._fail_ids is None or unit.id in self._fail_ids
        ):
            raise self._apply_error


class FakeSink:
    """In-memory projection sink: records every rendered config.

    `seeded` marks configs as ALREADY rendered ("proj/prod"), which is the
    steady state most tests run in -- an unrendered config correctly forces an
    unconditional export, and that has its own test.
    """

    def __init__(
        self,
        fail: Exception | None = None,
        seeded: Iterable[str] = (),
    ) -> None:
        self.files: dict[tuple[str, str], dict[str, str]] = {
            (ref.split("/")[0], ref.split("/")[1]): {} for ref in seeded
        }
        self.writes: list[tuple[str, str]] = []
        self._fail = fail

    def write(
        self, project: str, config: str, secrets: Mapping[str, str]
    ) -> str:
        if self._fail is not None:
            raise self._fail
        self.files[(project, config)] = dict(secrets)
        self.writes.append((project, config))
        return f"memory://{project}-{config}.env"

    def exists(self, project: str, config: str) -> bool:
        return (project, config) in self.files


@pytest.fixture
def make_unit():
    def _make(
        unit_id: str, name: str | None = None, lifecycle: Any = None
    ) -> Unit:
        unit = Unit(id=unit_id, name=name or unit_id, raw=None)
        if lifecycle is not None:
            unit.lifecycle = lifecycle
        return unit

    return _make


def run_pass(
    driver: FakeDriver,
    client: FakeSsmClient,
    *,
    trigger: Trigger = "poll",
    sink: FakeSink | None = None,
    adoptions: AdoptionCache | None = None,
    bootstrap: tuple[ConfigRef, ...] = (),
) -> None:
    """Run one real reconcile pass over in-memory fakes.

    The only seam stubbed is I/O: the driver (Docker) and the client (HTTP).
    The decision logic under test is the real `Reconciler`.
    """
    Reconciler(
        driver,
        # The client seam is a concrete class, not a Protocol (there is one
        # real implementation); the fake stands in for it only in tests.
        cast("SsmClient", client),
        HOST,
        Projector(sink if sink is not None else FakeSink(seeded=PROJECTED)),
        bootstrap_configs=bootstrap,
        adoptions=adoptions,
    ).run(trigger)

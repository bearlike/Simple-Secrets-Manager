from __future__ import annotations

from ssm_reload.errors import BindingError, DriverError, SsmClientError
from ssm_reload.models import Binding, Unit
from ssm_reload.reconcile import reconcile
from tests.reload.conftest import FakeDriver, FakeSsmClient

HOST = "host-1"


def _unit(uid: str) -> Unit:
    return Unit(id=uid, name=uid, raw=None)


def test_304_is_a_noop():
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("proj", "prod", '"v1"')})
    client = FakeSsmClient({("proj", "prod"): (False, None, None)})

    reconcile(driver, client, HOST)

    assert driver.applied == []
    assert client.reports == []
    assert client.export_calls == [("proj", "prod", '"v1"')]


def test_200_applies_and_reports_each_bound_unit():
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("proj", "prod", '"v1"')})
    secrets = {"API_KEY": "xyz"}
    client = FakeSsmClient({("proj", "prod"): (True, secrets, '"v2"')})

    reconcile(driver, client, HOST)

    assert driver.applied == [("c1", secrets, '"v2"')]
    assert client.reports == [
        {
            "project": "proj",
            "config": "prod",
            "container": "c1",
            "host": HOST,
            "from_revision": '"v1"',
            "to_revision": '"v2"',
        }
    ]


def test_dedup_one_export_for_many_units_on_same_config():
    units = [_unit("c1"), _unit("c2"), _unit("c3")]
    bindings = {
        "c1": Binding("proj", "prod", '"v1"'),
        "c2": Binding("proj", "prod", '"v1"'),
        "c3": Binding("proj", "prod", '"v1"'),
    }
    driver = FakeDriver(units, bindings)
    client = FakeSsmClient({("proj", "prod"): (True, {"K": "v"}, '"v2"')})

    reconcile(driver, client, HOST)

    # Exactly ONE conditional export despite three containers...
    assert len(client.export_calls) == 1
    # ...but all three containers recreated + reported.
    assert {c[0] for c in driver.applied} == {"c1", "c2", "c3"}
    assert len(client.reports) == 3


def test_mixed_revisions_apply_only_divergent_units():
    units = [_unit("c1"), _unit("c2")]
    bindings = {
        "c1": Binding("proj", "prod", '"v2"'),  # already current
        "c2": Binding("proj", "prod", '"v1"'),  # stale
    }
    driver = FakeDriver(units, bindings)
    client = FakeSsmClient({("proj", "prod"): (True, {"K": "v"}, '"v2"')})

    reconcile(driver, client, HOST)

    # Disagreeing revisions => unconditional export (etag None).
    assert client.export_calls == [("proj", "prod", None)]
    # Only the stale container is recreated.
    assert [c[0] for c in driver.applied] == ["c2"]
    assert len(client.reports) == 1


def test_ssm_error_recreates_nothing():
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("proj", "prod", '"v1"')})
    client = FakeSsmClient(
        {("proj", "prod"): SsmClientError("boom", status_code=500)}
    )

    reconcile(driver, client, HOST)

    assert driver.applied == []
    assert client.reports == []


def test_forbidden_is_skipped_and_logged(caplog):
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("proj", "prod", None)})
    client = FakeSsmClient(
        {("proj", "prod"): SsmClientError("no", status_code=403)}
    )

    with caplog.at_level("WARNING"):
        reconcile(driver, client, HOST)

    assert driver.applied == []
    assert any("403" in rec.message for rec in caplog.records)


def test_apply_failure_is_not_reported():
    # A failed recreate must never be stamped as a success: report_reload
    # is only called after apply() returns without raising.
    unit = _unit("c1")
    driver = FakeDriver(
        [unit],
        {"c1": Binding("proj", "prod", '"v1"')},
        apply_error=DriverError("recreate failed"),
    )
    client = FakeSsmClient({("proj", "prod"): (True, {"K": "v"}, '"v2"')})

    reconcile(driver, client, HOST)

    assert [c[0] for c in driver.applied] == ["c1"]  # attempted...
    assert client.reports == []  # ...but NOT reported.


def test_binding_parse_error_skips_that_unit_only():
    units = [_unit("good"), _unit("bad")]
    bindings: dict[str, Binding | Exception] = {
        "good": Binding("proj", "prod", '"v1"'),
        "bad": BindingError("malformed"),
    }
    driver = FakeDriver(units, bindings)
    client = FakeSsmClient({("proj", "prod"): (True, {"K": "v"}, '"v2"')})

    reconcile(driver, client, HOST)

    assert [c[0] for c in driver.applied] == ["good"]

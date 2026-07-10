"""Per-cycle status reporting: every pass emits one report per config group.

The transparency feature turns each reconcile pass into a heartbeat — even
the steady-state 304 — so the server's fleet view reflects every poll. These
tests pin the report accumulation, the group/unit outcome semantics, best-
effort delivery, and trigger threading.
"""

from __future__ import annotations

from ssm_reload.errors import DriverError, SsmClientError, SsmReloadError
from ssm_reload.models import Binding, Unit
from tests.reload.conftest import HOST, FakeDriver, FakeSsmClient, run_pass


def _unit(uid: str) -> Unit:
    return Unit(id=uid, name=uid, raw=None)


def _only_report(client: FakeSsmClient) -> dict:
    assert len(client.status_reports) == 1
    return client.status_reports[0]


def test_304_steady_state_reports_current_with_all_units():
    # The whole point: a 304 poll still produces a report listing every unit.
    units = [_unit("c1"), _unit("c2")]
    driver = FakeDriver(
        units,
        {
            "c1": Binding("proj", "prod", '"v1"'),
            "c2": Binding("proj", "prod", '"v1"'),
        },
    )
    client = FakeSsmClient({("proj", "prod"): (False, None, None)})

    run_pass(driver, client)

    report = _only_report(client)
    assert report["outcome"] == "current"
    assert report["revision"] == '"v1"'  # the confirmed-unchanged revision
    assert report["trigger"] == "poll"
    assert report["reporter"]["host"] == HOST
    assert report["reporter"]["version"]  # package version threaded through
    outcomes = {u["id"]: u["outcome"] for u in report["units"]}
    assert outcomes == {"c1": "current", "c2": "current"}
    assert driver.applied == []


def test_200_recreate_reports_updated_and_unit_recreated():
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("proj", "prod", '"v1"')})
    client = FakeSsmClient({("proj", "prod"): (True, {"K": "v"}, '"v2"')})

    run_pass(driver, client)

    report = _only_report(client)
    assert report["outcome"] == "updated"
    assert report["revision"] == '"v2"'
    assert report["units"][0]["outcome"] == "recreated"
    assert report["units"][0]["heldRevision"] == '"v1"'
    assert report["units"][0]["error"] is None


def test_recreate_failure_reports_unit_failed_and_group_error():
    # A group whose only divergent unit fails is "error"; the unit is "failed"
    # and carries the driver error string.
    unit = _unit("c1")
    driver = FakeDriver(
        [unit],
        {"c1": Binding("proj", "prod", '"v1"')},
        apply_error=DriverError("recreate failed"),
    )
    client = FakeSsmClient({("proj", "prod"): (True, {"K": "v"}, '"v2"')})

    run_pass(driver, client)

    report = _only_report(client)
    assert report["outcome"] == "error"
    assert report["units"][0]["outcome"] == "failed"
    assert "recreate failed" in report["units"][0]["error"]
    # A failed recreate is never reported to /reload/events as a success.
    assert client.reports == []


def test_mixed_success_and_failure_group_is_updated():
    # Semantics pinned: any successful recreate makes the group "updated",
    # even alongside a failure.
    units = [_unit("ok"), _unit("bad")]
    driver = FakeDriver(
        units,
        {
            "ok": Binding("proj", "prod", '"v1"'),
            "bad": Binding("proj", "prod", '"v1"'),
        },
        apply_error=DriverError("boom"),
        fail_ids={"bad"},
    )
    client = FakeSsmClient({("proj", "prod"): (True, {"K": "v"}, '"v2"')})

    run_pass(driver, client)

    report = _only_report(client)
    assert report["outcome"] == "updated"
    outcomes = {u["id"]: u["outcome"] for u in report["units"]}
    assert outcomes == {"ok": "recreated", "bad": "failed"}


def test_export_error_reports_error_with_skipped_units():
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("proj", "prod", '"v1"')})
    client = FakeSsmClient(
        {("proj", "prod"): SsmClientError("boom", status_code=500)}
    )

    run_pass(driver, client)

    report = _only_report(client)
    assert report["outcome"] == "error"
    assert report["error"] == "boom"
    assert report["revision"] is None
    assert report["units"][0]["outcome"] == "skipped"
    assert driver.applied == []


def test_report_post_failure_does_not_break_reconcile():
    # A failed status POST is best-effort: the recreate still happens and the
    # pass completes without raising.
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("proj", "prod", '"v1"')})
    client = FakeSsmClient(
        {("proj", "prod"): (True, {"K": "v"}, '"v2"')},
        status_error=SsmReloadError("report endpoint down"),
    )

    run_pass(driver, client)  # must not raise

    assert [c[0] for c in driver.applied] == ["c1"]
    assert len(client.status_reports) == 1  # attempted


def test_trigger_is_threaded_into_the_report():
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("proj", "prod", '"v1"')})
    client = FakeSsmClient({("proj", "prod"): (False, None, None)})

    run_pass(driver, client, trigger="event")

    assert _only_report(client)["trigger"] == "event"


def test_one_report_per_config_group():
    # Two configs -> two independent reports in one pass.
    units = [_unit("a"), _unit("b")]
    driver = FakeDriver(
        units,
        {
            "a": Binding("proj", "prod", '"v1"'),
            "b": Binding("proj", "stage", '"v1"'),
        },
    )
    client = FakeSsmClient(
        {
            ("proj", "prod"): (False, None, None),
            ("proj", "stage"): (False, None, None),
        }
    )

    run_pass(driver, client)

    configs = {r["config"] for r in client.status_reports}
    assert configs == {"prod", "stage"}


def test_group_failure_does_not_starve_other_groups():
    # A non-SsmReloadError exploding inside one group's processing must
    # not abort the pass: config groups are independent, so the healthy
    # group still exports and reports every cycle.
    units = [_unit("bad"), _unit("good")]
    driver = FakeDriver(
        units,
        {
            "bad": Binding("badproj", "prod", None),
            "good": Binding("web", "prod", '"v1"'),
        },
    )
    client = FakeSsmClient(
        {
            ("badproj", "prod"): RuntimeError("boom"),
            ("web", "prod"): (False, None, None),
        }
    )

    run_pass(driver, client)

    assert ("web", "prod", '"v1"') in client.export_calls
    report = _only_report(client)
    assert (report["project"], report["config"]) == ("web", "prod")
    assert report["outcome"] == "current"

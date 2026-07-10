from __future__ import annotations

from ssm_reload.errors import BindingError, DriverError, SsmClientError
from ssm_reload.models import Binding, ConfigRef, Dependent, Lifecycle, Unit
from ssm_reload.reconcile import AdoptionCache
from tests.reload.conftest import (
    HOST,
    FakeDriver,
    FakeSink,
    FakeSsmClient,
    run_pass,
)


def _unit(uid: str) -> Unit:
    return Unit(id=uid, name=uid, raw=None)


def test_304_is_a_noop():
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("proj", "prod", '"v1"')})
    client = FakeSsmClient({("proj", "prod"): (False, None, None)})

    run_pass(driver, client)

    assert driver.applied == []
    assert client.reports == []
    assert client.export_calls == [("proj", "prod", '"v1"')]


def test_200_applies_and_reports_each_bound_unit():
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("proj", "prod", '"v1"')})
    secrets = {"API_KEY": "xyz"}
    client = FakeSsmClient({("proj", "prod"): (True, secrets, '"v2"')})

    run_pass(driver, client)

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

    run_pass(driver, client)

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

    run_pass(driver, client)

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

    run_pass(driver, client)

    assert driver.applied == []
    assert client.reports == []


def test_forbidden_is_skipped_and_logged(caplog):
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("proj", "prod", None)})
    client = FakeSsmClient(
        {("proj", "prod"): SsmClientError("no", status_code=403)}
    )

    with caplog.at_level("WARNING"):
        run_pass(driver, client)

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

    run_pass(driver, client)

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

    run_pass(driver, client)

    assert [c[0] for c in driver.applied] == ["good"]


# --- adoption-by-comparison: co-managed containers -----------------------
#
# An external owner (compose/Portainer redeploy, Watchtower) recreates an
# opted-in container from a spec that carries the operator-set enable/config
# labels but NOT the reloader-stamped revision label. held_revision reads
# None; the reloader must judge divergence by the container's ACTUAL env,
# not blind-recreate.


def test_unlabeled_unit_with_current_env_is_adopted_not_recreated():
    unit = _unit("c1")
    driver = FakeDriver(
        [unit],
        {"c1": Binding("proj", "prod", None)},
        # Superset: app-native env alongside the managed keys must not
        # block adoption.
        envs={"c1": {"API_KEY": "xyz", "PATH": "/usr/bin"}},
    )
    client = FakeSsmClient(
        {("proj", "prod"): (True, {"API_KEY": "xyz"}, '"v2"')}
    )

    run_pass(driver, client)

    assert driver.applied == []  # no recreate
    assert client.reports == []  # no reload event
    assert client.status_reports[-1]["outcome"] == "current"


def test_unlabeled_unit_with_stale_env_is_recreated():
    unit = _unit("c1")
    driver = FakeDriver(
        [unit],
        {"c1": Binding("proj", "prod", None)},
        envs={"c1": {"API_KEY": "old-value"}},
    )
    secrets = {"API_KEY": "xyz"}
    client = FakeSsmClient({("proj", "prod"): (True, secrets, '"v2"')})

    run_pass(driver, client)

    assert driver.applied == [("c1", secrets, '"v2"')]


def test_unlabeled_unit_missing_a_managed_key_is_recreated():
    unit = _unit("c1")
    driver = FakeDriver(
        [unit],
        {"c1": Binding("proj", "prod", None)},
        envs={"c1": {"OTHER": "x"}},
    )
    secrets = {"API_KEY": "xyz"}
    client = FakeSsmClient({("proj", "prod"): (True, secrets, '"v2"')})

    run_pass(driver, client)

    assert [c[0] for c in driver.applied] == ["c1"]


def test_env_read_failure_falls_back_to_recreate():
    # Fail toward known-good secrets, never fail open on an unverifiable
    # container.
    unit = _unit("c1")
    driver = FakeDriver(
        [unit],
        {"c1": Binding("proj", "prod", None)},
        envs={"c1": DriverError("inspect failed")},
    )
    secrets = {"API_KEY": "xyz"}
    client = FakeSsmClient({("proj", "prod"): (True, secrets, '"v2"')})

    run_pass(driver, client)

    assert [c[0] for c in driver.applied] == ["c1"]


def test_adoption_enables_304_fast_path_on_next_pass():
    unit = _unit("c1")
    driver = FakeDriver(
        [unit],
        {"c1": Binding("proj", "prod", None)},
        envs={"c1": {"API_KEY": "xyz"}},
    )
    cache = AdoptionCache()

    first = FakeSsmClient(
        {("proj", "prod"): (True, {"API_KEY": "xyz"}, '"v2"')}
    )
    run_pass(driver, first, adoptions=cache)
    # Unlabeled unit forces an unconditional export on the adoption pass.
    assert first.export_calls == [("proj", "prod", None)]

    second = FakeSsmClient({("proj", "prod"): (False, None, None)})
    run_pass(driver, second, adoptions=cache)
    # The adopted revision is remembered, restoring the If-None-Match/304
    # fast path even though the container still has no revision label.
    assert second.export_calls == [("proj", "prod", '"v2"')]
    assert driver.applied == []


def test_adoption_cache_prunes_units_that_disappear():
    unit = _unit("c1")
    driver = FakeDriver(
        [unit],
        {"c1": Binding("proj", "prod", None)},
        envs={"c1": {"API_KEY": "xyz"}},
    )
    cache = AdoptionCache()
    client = FakeSsmClient(
        {("proj", "prod"): (True, {"API_KEY": "xyz"}, '"v2"')}
    )
    run_pass(driver, client, adoptions=cache)
    assert cache.get("c1") == '"v2"'

    # The container is gone next pass (its id can never come back --
    # recreates mint new ids), so its entry must not linger.
    empty_driver = FakeDriver([], {})
    run_pass(empty_driver, FakeSsmClient({}), adoptions=cache)
    assert cache.get("c1") is None


# --- lifecycle invariants: SSM never takes a container from its owner ----
#
# All four failures below were reproduced live while a Portainer/compose
# stack was deploying: the reloader renamed compose's container aside
# mid-deploy ("dependency failed to start: container vpn-gluetun-1-ssmold
# exited (1)"), replaced its whole env, and orphaned the netns dependent.


def _owned(uid: str, owner: str = "vpn-stremio") -> Unit:
    unit = _unit(uid)
    unit.lifecycle = Lifecycle(owner=owner)
    return unit


def test_compose_owned_container_is_never_recreated():
    unit = _owned("c1")
    driver = FakeDriver([unit], {"c1": Binding("vpn", "zurich", '"v1"')})
    client = FakeSsmClient({("vpn", "zurich"): (True, {"K": "v"}, '"v2"')})

    run_pass(driver, client)

    # The whole point: compose owns this container's lifecycle. Recreating
    # it races an in-flight `compose up` and destroys the deploy.
    assert driver.applied == []
    assert client.reports == []
    status = client.status_reports[-1]
    assert status["units"][0]["outcome"] == "skipped"
    assert "vpn-stremio" in status["units"][0]["error"]
    # Divergence is REPORTED, loudly: the workload is running stale secrets
    # until its owner redeploys it.
    assert status["outcome"] == "error"


def test_container_born_with_correct_secrets_is_adopted_not_restarted():
    # The steady state of the new design: compose creates the container
    # WITH the projected env_file, so its env already matches. Adopt it.
    unit = _owned("c1")
    driver = FakeDriver(
        [unit],
        {"c1": Binding("vpn", "zurich", None)},
        envs={"c1": {"WG_KEY": "abc", "VPN_SERVICE_PROVIDER": "protonvpn"}},
    )
    client = FakeSsmClient(
        {("vpn", "zurich"): (True, {"WG_KEY": "abc"}, '"v2"')}
    )

    run_pass(driver, client)

    assert driver.applied == []
    status = client.status_reports[-1]
    assert status["outcome"] == "current"
    assert status["units"][0]["outcome"] == "current"


def test_container_still_settling_is_left_alone():
    unit = _unit("c1")
    unit.lifecycle = Lifecycle(age_seconds=3.0)
    driver = FakeDriver([unit], {"c1": Binding("vpn", "zurich", '"v1"')})
    client = FakeSsmClient({("vpn", "zurich"): (True, {"K": "v"}, '"v2"')})

    run_pass(driver, client)

    # Three seconds old: another tool is mid-deploy. Yanking it now is
    # exactly what destroyed stack 274.
    assert driver.applied == []
    assert client.status_reports[-1]["units"][0]["outcome"] == "skipped"


def test_container_that_has_not_started_yet_is_left_alone():
    unit = _unit("c1")
    # `created` but never started: compose has made it and is about to
    # start it. Its age may already exceed the settling window on a slow
    # image pull, so status must gate independently of age.
    unit.lifecycle = Lifecycle(status="created", age_seconds=600.0)
    driver = FakeDriver([unit], {"c1": Binding("vpn", "zurich", '"v1"')})
    client = FakeSsmClient({("vpn", "zurich"): (True, {"K": "v"}, '"v2"')})

    run_pass(driver, client)

    assert driver.applied == []


def test_netns_donor_with_an_owned_dependent_is_not_recreated():
    donor = _unit("gluetun")
    donor.lifecycle = Lifecycle(
        dependents=(
            Dependent(
                id="stremio", name="t-stremio-server", owner="vpn-stremio"
            ),
        )
    )
    driver = FakeDriver([donor], {"gluetun": Binding("vpn", "zurich", '"v1"')})
    client = FakeSsmClient({("vpn", "zurich"): (True, {"K": "v"}, '"v2"')})

    run_pass(driver, client)

    # Recreating the donor mints a new id; `t-stremio-server` would be left
    # attached to a dead namespace and SSM may not touch it (compose owns
    # it). Refuse, and say why.
    assert driver.applied == []
    error = client.status_reports[-1]["units"][0]["error"]
    assert "t-stremio-server" in error


def test_netns_donor_with_no_other_owner_is_converged():
    donor = _unit("gluetun")
    donor.lifecycle = Lifecycle(
        dependents=(Dependent(id="sidecar", name="sidecar", owner=None),)
    )
    driver = FakeDriver([donor], {"gluetun": Binding("vpn", "zurich", '"v1"')})
    client = FakeSsmClient({("vpn", "zurich"): (True, {"K": "v"}, '"v2"')})

    run_pass(driver, client)

    # Nobody else owns the dependent, so the driver may recreate the donor
    # and carry its passenger across to the new namespace.
    assert [c[0] for c in driver.applied] == ["gluetun"]


def test_a_key_removed_from_the_config_blocks_adoption():
    # Subset comparison alone cannot see a key DELETED from the config that
    # lingers in the container's env; the keys label makes it visible, and a
    # recreate prunes it.
    unit = _unit("c1")
    driver = FakeDriver(
        [unit],
        {"c1": Binding("vpn", "zurich", None)},
        envs={"c1": {"KEPT": "v", "REMOVED": "stale"}},
        managed_keys={"c1": {"KEPT", "REMOVED"}},
    )
    client = FakeSsmClient({("vpn", "zurich"): (True, {"KEPT": "v"}, '"v2"')})

    run_pass(driver, client)

    assert [c[0] for c in driver.applied] == ["c1"]


# --- projection: delivery happens before (and independently of) recreate -


def test_projection_renders_the_config_on_a_changed_export():
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("vpn", "zurich", '"v1"')})
    secrets = {"WIREGUARD_PRIVATE_KEY": "abc"}
    client = FakeSsmClient({("vpn", "zurich"): (True, secrets, '"v2"')})
    sink = FakeSink()

    run_pass(driver, client, sink=sink)

    assert sink.files[("vpn", "zurich")] == secrets


def test_projection_failure_never_blocks_the_reconcile_pass():
    # A best-effort side effect: a broken sink must not stop secrets from
    # reaching the containers that still need a recreate.
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("vpn", "zurich", '"v1"')})
    client = FakeSsmClient({("vpn", "zurich"): (True, {"K": "v"}, '"v2"')})
    sink = FakeSink(fail=OSError("read-only file system"))

    run_pass(driver, client, sink=sink)

    assert [c[0] for c in driver.applied] == ["c1"]


def test_projection_failure_is_reported_not_silently_swallowed():
    # Delivery is the primary path now: a broken sink means containers will be
    # BORN wrong. Reporting the group "current" would leave an operator staring
    # at a green fleet view and a stack that cannot start.
    unit = _unit("c1")
    driver = FakeDriver(
        [unit],
        {"c1": Binding("vpn", "zurich", None)},
        envs={"c1": {"K": "v"}},  # nothing to recreate: env already matches
    )
    client = FakeSsmClient({("vpn", "zurich"): (True, {"K": "v"}, '"v2"')})

    run_pass(driver, client, sink=FakeSink(fail=OSError("read-only fs")))

    status = client.status_reports[-1]
    assert status["outcome"] == "error"
    assert "read-only fs" in status["error"]


def test_a_bootstrap_config_that_cannot_be_written_reports_the_failure():
    # The group has NO units, so no unit outcome could ever go red — the
    # projection error is the only thing that can carry the failure.
    driver = FakeDriver([], {})
    client = FakeSsmClient({("vpn", "zurich"): (True, {"K": "v"}, '"v2"')})

    run_pass(
        driver,
        client,
        sink=FakeSink(fail=OSError("permission denied")),
        bootstrap=(ConfigRef("vpn", "zurich"),),
    )

    status = client.status_reports[-1]
    assert status["outcome"] == "error"
    assert "permission denied" in status["error"]


def test_the_group_error_names_the_divergence_a_human_must_act_on():
    # A settling unit also reports "skipped" with a reason; the group error
    # must be the one that needs a REDEPLOY, not the one that resolves itself.
    settling = _unit("c1")
    settling.lifecycle = Lifecycle(age_seconds=3.0)
    owned = _owned("c2")
    driver = FakeDriver(
        [settling, owned],
        {
            "c1": Binding("vpn", "zurich", '"v1"'),
            "c2": Binding("vpn", "zurich", '"v1"'),
        },
    )
    client = FakeSsmClient({("vpn", "zurich"): (True, {"K": "v"}, '"v2"')})

    run_pass(driver, client)

    error = client.status_reports[-1]["error"]
    assert "vpn-stremio" in error  # the compose-owned one
    assert "settling window" not in error


def test_a_missing_projection_file_forces_an_unconditional_export():
    # The tmpfs volume is EMPTY after a reboot (or after the last holder
    # exits), while the containers still carry their revision label -- a
    # conditional export would 304 and the file would never come back.
    unit = _unit("c1")
    driver = FakeDriver(
        [unit],
        {"c1": Binding("vpn", "zurich", '"v2"')},
        envs={"c1": {"K": "v"}},
    )
    client = FakeSsmClient({("vpn", "zurich"): (True, {"K": "v"}, '"v2"')})
    sink = FakeSink()

    run_pass(driver, client, sink=sink)

    assert client.export_calls == [("vpn", "zurich", None)]
    assert sink.files[("vpn", "zurich")] == {"K": "v"}
    assert driver.applied == []  # env already current -> nothing to do


def test_an_already_projected_config_keeps_the_304_fast_path():
    unit = _unit("c1")
    driver = FakeDriver([unit], {"c1": Binding("vpn", "zurich", '"v2"')})
    sink = FakeSink()
    sink.write("vpn", "zurich", {"K": "v"})

    client = FakeSsmClient({("vpn", "zurich"): (False, None, None)})
    run_pass(driver, client, sink=sink)

    assert client.export_calls == [("vpn", "zurich", '"v2"')]


def test_a_config_with_no_container_is_still_materialized():
    # Bootstrap: `env_file` must EXIST before the first `compose up`, and on
    # a first deploy no container is bound to the config yet.
    driver = FakeDriver([], {})
    client = FakeSsmClient({("vpn", "zurich"): (True, {"K": "v"}, '"v2"')})
    sink = FakeSink()

    run_pass(
        driver,
        client,
        sink=sink,
        bootstrap=(ConfigRef("vpn", "zurich"),),
    )

    assert sink.files[("vpn", "zurich")] == {"K": "v"}
    assert client.status_reports[-1]["units"] == []

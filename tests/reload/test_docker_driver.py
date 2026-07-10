from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from ssm_reload.config import ENABLE_LABEL, TMPFS_VOLUME_OPTS
from ssm_reload.docker_driver import (
    DockerDriver,
    _typed_kwargs,
    build_recreate_spec,
)
from ssm_reload.errors import BindingError, DriverError
from ssm_reload.models import Unit

ATTRS: dict[str, Any] = {
    "Id": "abc123def456ghijklmnop",
    "Name": "/web",
    "Config": {
        "Image": "nginx:1.25",
        "Cmd": ["nginx", "-g", "daemon off;"],
        "Entrypoint": ["/entry.sh"],
        "WorkingDir": "/app",
        "User": "1000:1000",
        "Env": ["PATH=/usr/bin", "SECRET_OLD=old"],
        "Labels": {
            "com.bearlike.ssm.enable": "true",
            "com.bearlike.ssm.config": "proj/prod",
            "com.bearlike.ssm.revision": '"v1"',
            "com.example.team": "payments",
        },
        "Healthcheck": {
            "Test": ["CMD", "curl", "-f", "localhost"],
            "Interval": 30000000000,
            "Timeout": 3000000000,
            "Retries": 3,
            "StartPeriod": 0,
        },
    },
    "HostConfig": {
        "RestartPolicy": {
            "Name": "unless-stopped",
            "MaximumRetryCount": 0,
        },
        "PortBindings": {
            "80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}],
            "443/tcp": [{"HostIp": "", "HostPort": "8443"}],
        },
        "NetworkMode": "frontend",
        "LogConfig": {"Type": "json-file", "Config": {"max-size": "10m"}},
        "Memory": 536870912,
        "NanoCpus": 500000000,
        "CapAdd": ["NET_ADMIN"],
        "Privileged": False,
    },
    "Mounts": [
        {
            "Type": "volume",
            "Name": "data",
            "Destination": "/var/data",
            "RW": True,
        },
        {
            "Type": "bind",
            "Source": "/etc/host.conf",
            "Destination": "/etc/app.conf",
            "RW": False,
        },
    ],
    "NetworkSettings": {
        "Networks": {
            "frontend": {
                "Aliases": ["web", "abc123def456"],
                "IPAMConfig": {"IPv4Address": "172.20.0.5"},
            },
            "backend": {
                "Aliases": ["web-internal"],
                "IPAMConfig": None,
            },
        }
    },
}


def test_build_spec_merges_secrets_over_the_containers_own_env():
    # THE defect this whole design exists to kill: the old spec set
    # "environment": dict(env), so every variable the container got from its
    # compose file but which is absent from the SSM config was silently
    # dropped on recreate (gluetun lost VPN_SERVICE_PROVIDER and died).
    spec = build_recreate_spec(ATTRS, {"SECRET_NEW": "new"}, '"v2"')
    kwargs = spec.create_kwargs

    assert kwargs["environment"] == {
        "PATH": "/usr/bin",  # app-native env SURVIVES
        "SECRET_OLD": "old",
        "SECRET_NEW": "new",  # fresh secret overlaid on top
    }
    # Revision label bumped; other labels preserved.
    assert kwargs["labels"]["com.bearlike.ssm.revision"] == '"v2"'
    assert kwargs["labels"]["com.example.team"] == "payments"
    assert kwargs["labels"]["com.bearlike.ssm.config"] == "proj/prod"


def test_build_spec_stamps_the_injected_key_names_as_a_label():
    spec = build_recreate_spec(ATTRS, {"B": "2", "A": "1"}, '"v2"')

    # Sorted + comma-joined: this label is what makes the NEXT recreate able
    # to tell "SSM injected this key" from "the app has always had it".
    assert spec.create_kwargs["labels"]["com.bearlike.ssm.keys"] == "A,B"


def test_build_spec_prunes_keys_removed_from_the_config():
    attrs = {
        **ATTRS,
        "Config": {
            **ATTRS["Config"],
            "Env": ["APP_NATIVE=keep", "OLD_KEY=stale", "KEPT_KEY=v1"],
            "Labels": {
                **ATTRS["Config"]["Labels"],
                "com.bearlike.ssm.keys": "OLD_KEY,KEPT_KEY",
            },
        },
    }

    spec = build_recreate_spec(attrs, {"KEPT_KEY": "v2"}, '"v2"')

    # OLD_KEY was ours and is gone from the config -> pruned. A naive merge
    # would leak it into the container forever.
    assert spec.create_kwargs["environment"] == {
        "APP_NATIVE": "keep",
        "KEPT_KEY": "v2",
    }
    assert spec.create_kwargs["labels"]["com.bearlike.ssm.keys"] == "KEPT_KEY"


def test_build_spec_drops_env_that_only_mirrors_the_image_defaults():
    # Cloning image-provided env into the container's own env would pin the
    # image's CURRENT defaults forever: an image upgrade that changes PATH
    # would never reach the container again.
    spec = build_recreate_spec(
        ATTRS,
        {"SECRET_NEW": "new"},
        '"v2"',
        image_env=["PATH=/usr/bin"],
    )

    assert spec.create_kwargs["environment"] == {
        "SECRET_OLD": "old",
        "SECRET_NEW": "new",
    }


def test_build_spec_can_repoint_network_mode_at_a_new_donor():
    attrs = {
        "Config": {"Image": "busybox", "Env": []},
        "HostConfig": {"NetworkMode": "container:olddonor"},
    }

    spec = build_recreate_spec(
        attrs, {}, None, network_mode="container:newdonor"
    )

    assert spec.create_kwargs["network_mode"] == "container:newdonor"


def test_build_spec_without_a_revision_leaves_the_labels_untouched():
    # Re-pointing a netns dependent recreates a container SSM does not
    # manage; it must not acquire SSM's labels as a side effect.
    spec = build_recreate_spec(ATTRS, {}, None)

    labels = spec.create_kwargs["labels"]
    assert labels["com.bearlike.ssm.revision"] == '"v1"'
    assert "com.bearlike.ssm.keys" not in labels


def test_build_spec_preserves_core_runtime_fields():
    spec = build_recreate_spec(ATTRS, {}, '"v2"')
    kwargs = spec.create_kwargs
    assert kwargs["image"] == "nginx:1.25"
    assert kwargs["name"] == "web"
    assert kwargs["command"] == ["nginx", "-g", "daemon off;"]
    assert kwargs["entrypoint"] == ["/entry.sh"]
    assert kwargs["working_dir"] == "/app"
    assert kwargs["user"] == "1000:1000"
    assert kwargs["healthcheck"]["Test"][0] == "CMD"
    assert kwargs["log_config"]["Type"] == "json-file"
    assert kwargs["mem_limit"] == 536870912
    assert kwargs["nano_cpus"] == 500000000
    assert kwargs["cap_add"] == ["NET_ADMIN"]


def test_build_spec_preserves_restart_ports_and_mounts():
    spec = build_recreate_spec(ATTRS, {}, '"v2"')
    kwargs = spec.create_kwargs
    assert kwargs["restart_policy"] == {
        "Name": "unless-stopped",
        "MaximumRetryCount": 0,
    }
    assert kwargs["ports"] == {
        "80/tcp": ("0.0.0.0", 8080),
        "443/tcp": 8443,
    }
    assert kwargs["volumes"] == {
        "data": {"bind": "/var/data", "mode": "rw"},
        "/etc/host.conf": {"bind": "/etc/app.conf", "mode": "ro"},
    }


def test_build_spec_preserves_networks_with_aliases():
    spec = build_recreate_spec(ATTRS, {}, '"v2"')
    assert spec.primary_network == "frontend"
    assert spec.create_kwargs["network"] == "frontend"
    # The stale container-id alias is filtered out.
    assert spec.networks["frontend"] == {
        "aliases": ["web"],
        "ipv4_address": "172.20.0.5",
    }
    assert spec.networks["backend"] == {"aliases": ["web-internal"]}


def test_build_spec_special_network_mode_uses_network_mode():
    attrs = {
        "Config": {"Image": "busybox"},
        "HostConfig": {"NetworkMode": "host"},
        "NetworkSettings": {"Networks": {"host": {}}},
    }
    spec = build_recreate_spec(attrs, {}, '"v2"')
    assert spec.create_kwargs["network_mode"] == "host"
    assert "network" not in spec.create_kwargs
    assert spec.networks == {}


# --- read_binding label parsing -----------------------------------


class FakeContainer:
    def __init__(self, labels: dict[str, str], attrs: Any = None) -> None:
        self.labels = labels
        self.attrs = attrs or {}
        self.id = self.attrs.get("Id") or ""
        self.name = (self.attrs.get("Name") or "").lstrip("/")
        self.stopped = False
        self.removed = False
        self.started = False
        self.renamed_to: str | None = None

    def stop(self) -> None:
        self.stopped = True

    def start(self) -> None:
        self.started = True

    def rename(self, name: str) -> None:
        self.renamed_to = name
        self.name = name

    def remove(self, **_kwargs: Any) -> None:
        self.removed = True


def _driver_unit(labels: dict[str, str]) -> tuple[DockerDriver, Unit]:
    driver = DockerDriver(client=object())
    container = FakeContainer(labels)
    return driver, Unit(id="c1", name="web", raw=container)


def test_read_env_parses_inspect_env_entries():
    driver = DockerDriver(client=object())
    container = FakeContainer(
        {},
        attrs={
            "Config": {
                # A value containing '=' must split on the FIRST '=' only;
                # a bare KEY entry reads as empty string.
                "Env": ["API_KEY=xyz", "OPTS=a=b", "EMPTYVAL"]
            }
        },
    )
    unit = Unit(id="c1", name="web", raw=container)
    assert driver.read_env(unit) == {
        "API_KEY": "xyz",
        "OPTS": "a=b",
        "EMPTYVAL": "",
    }


def test_read_env_missing_config_reads_as_empty():
    driver = DockerDriver(client=object())
    unit = Unit(id="c1", name="web", raw=FakeContainer({}, attrs={}))
    assert driver.read_env(unit) == {}


def test_read_env_wraps_inspect_errors_as_driver_error():
    class ExplodingContainer:
        @property
        def attrs(self) -> dict[str, Any]:
            raise RuntimeError("daemon went away")

    driver = DockerDriver(client=object())
    unit = Unit(id="c1", name="web", raw=ExplodingContainer())
    with pytest.raises(DriverError, match="web"):
        driver.read_env(unit)


def test_read_binding_parses_project_config_and_revision():
    driver, unit = _driver_unit(
        {
            "com.bearlike.ssm.config": "proj/prod",
            "com.bearlike.ssm.revision": '"v9"',
        }
    )
    binding = driver.read_binding(unit)
    assert binding.project == "proj"
    assert binding.config == "prod"
    assert binding.held_revision == '"v9"'


def test_read_binding_missing_revision_is_none():
    driver, unit = _driver_unit({"com.bearlike.ssm.config": "proj/prod"})
    binding = driver.read_binding(unit)
    assert binding.held_revision is None


@pytest.mark.parametrize(
    "labels",
    [
        {},
        {"com.bearlike.ssm.config": "noslash"},
        {"com.bearlike.ssm.config": "/prod"},
        {"com.bearlike.ssm.config": "proj/"},
        # Non-slug halves must be rejected HERE: they would otherwise
        # survive grouping and abort the whole pass as a report
        # ValidationError (config groups must stay independent).
        {"com.bearlike.ssm.config": "MyApp/prod"},
        {"com.bearlike.ssm.config": "proj/pr od"},
    ],
)
def test_read_binding_rejects_bad_config_label(labels):
    driver, unit = _driver_unit(labels)
    with pytest.raises(BindingError):
        driver.read_binding(unit)


# --- apply() recreate flow with a fake SDK ------------------------


class FakeNetwork:
    def __init__(self, name: str) -> None:
        self.name = name
        self.connected: list[dict[str, Any]] = []
        self.disconnected = 0

    def connect(self, _container: Any, **kwargs: Any) -> None:
        self.connected.append(kwargs)

    def disconnect(self, _container: Any) -> None:
        self.disconnected += 1


class FakeNewContainer:
    def __init__(
        self,
        kwargs: dict[str, Any],
        *,
        fail_start: bool = False,
        container_id: str = "new-id",
    ) -> None:
        self.kwargs = kwargs
        self.id = container_id
        self.started = False
        self.removed = False
        self._fail_start = fail_start

    def start(self) -> None:
        if self._fail_start:
            raise RuntimeError("start boom")
        self.started = True

    def remove(self, **_kwargs: Any) -> None:
        self.removed = True


class FakeContainersApi:
    def __init__(
        self,
        *,
        fail_create: bool = False,
        fail_start: bool = False,
        existing_names: tuple[str, ...] = (),
        listed: tuple[Any, ...] = (),
    ) -> None:
        self.created: list[FakeNewContainer] = []
        self._fail_create = fail_create
        self._fail_start = fail_start
        self._existing = set(existing_names)
        self._listed = listed
        self.list_calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeNewContainer:
        if self._fail_create:
            raise RuntimeError("create boom")
        new = FakeNewContainer(
            kwargs,
            fail_start=self._fail_start,
            container_id=f"new-{len(self.created)}",
        )
        self.created.append(new)
        return new

    def list(self, **kwargs: Any) -> list[Any]:
        self.list_calls.append(kwargs)
        containers = list(self._listed)
        if kwargs.get("filters", {}).get("label"):
            containers = [c for c in containers if c.labels.get(ENABLE_LABEL)]
        return containers

    def get(self, key: str) -> Any:
        for container in self._listed:
            if getattr(container, "id", None) == key:
                return container
        if key in self._existing:
            return object()
        raise KeyError(key)


class FakeNetworksApi:
    def __init__(self) -> None:
        self.nets: dict[str, FakeNetwork] = {}

    def get(self, name: str) -> FakeNetwork:
        return self.nets.setdefault(name, FakeNetwork(name))


class FakeVolumesApi:
    def __init__(self, existing: dict[str, Any] | None = None) -> None:
        self.volumes = existing or {}
        self.created: list[dict[str, Any]] = []

    def get(self, name: str) -> Any:
        if name not in self.volumes:
            raise KeyError(name)
        return self.volumes[name]

    def create(self, **kwargs: Any) -> Any:
        self.created.append(kwargs)
        volume = SimpleNamespace(name=kwargs["name"], attrs={})
        self.volumes[kwargs["name"]] = volume
        return volume


class FakeImagesApi:
    def __init__(self, env: dict[str, list[str]] | None = None) -> None:
        self._env = env or {}

    def get(self, name: str) -> Any:
        if name not in self._env:
            raise KeyError(name)
        return SimpleNamespace(attrs={"Config": {"Env": self._env[name]}})


class FakeDockerClient:
    def __init__(
        self,
        *,
        fail_create: bool = False,
        fail_start: bool = False,
        existing_names: tuple[str, ...] = (),
        listed: tuple[Any, ...] = (),
        volumes: dict[str, Any] | None = None,
        image_env: dict[str, list[str]] | None = None,
    ) -> None:
        self.containers = FakeContainersApi(
            fail_create=fail_create,
            fail_start=fail_start,
            existing_names=existing_names,
            listed=listed,
        )
        self.networks = FakeNetworksApi()
        self.volumes = FakeVolumesApi(volumes)
        self.images = FakeImagesApi(image_env)


def test_apply_recreates_with_env_merged_and_networks_preserved():
    client = FakeDockerClient()
    driver = DockerDriver(client=client)
    old = FakeContainer(ATTRS["Config"]["Labels"], attrs=ATTRS)
    unit = Unit(id="c1", name="web", raw=old)

    driver.apply(unit, {"SECRET_NEW": "new"}, '"v2"')

    # Old container stopped + renamed aside, then removed only AFTER the
    # replacement started; new one created + started under the real name.
    assert old.stopped and old.removed
    assert old.renamed_to == "web-ssmold"
    new = client.containers.created[0]
    assert new.started is True
    assert new.kwargs["name"] == "web"
    assert new.kwargs["environment"] == {
        "PATH": "/usr/bin",
        "SECRET_OLD": "old",
        "SECRET_NEW": "new",
    }
    assert new.kwargs["network"] == "frontend"

    # Primary network reconnected with aliases; extra network connected.
    frontend = client.networks.nets["frontend"]
    backend = client.networks.nets["backend"]
    assert frontend.disconnected == 1
    assert frontend.connected == [
        {"aliases": ["web"], "ipv4_address": "172.20.0.5"}
    ]
    assert backend.connected == [{"aliases": ["web-internal"]}]


# --- apply() rollback: the original is never lost -----------------


def _running_attrs() -> dict[str, Any]:
    """ATTRS marked as a running container (drives rollback restart)."""
    return {**ATTRS, "State": {"Running": True}}


def test_apply_rolls_back_when_create_fails():
    client = FakeDockerClient(fail_create=True)
    driver = DockerDriver(client=client)
    old = FakeContainer(
        dict(ATTRS["Config"]["Labels"]), attrs=_running_attrs()
    )
    unit = Unit(id="c1", name="web", raw=old)

    with pytest.raises(DriverError):
        driver.apply(unit, {"SECRET_NEW": "new"}, '"v2"')

    # Original preserved: stopped + set aside, then renamed BACK.
    assert old.stopped is True
    assert old.removed is False
    assert old.renamed_to == "web"
    assert old.started is True  # was running -> restarted on rollback
    assert client.containers.created == []
    # Still carries its OLD revision -> stays DIVERGENT, retried next pass.
    assert old.labels["com.bearlike.ssm.revision"] == '"v1"'


def test_apply_rolls_back_when_start_fails():
    client = FakeDockerClient(fail_start=True)
    driver = DockerDriver(client=client)
    old = FakeContainer(
        dict(ATTRS["Config"]["Labels"]), attrs=_running_attrs()
    )
    unit = Unit(id="c1", name="web", raw=old)

    with pytest.raises(DriverError):
        driver.apply(unit, {"SECRET_NEW": "new"}, '"v2"')

    # The half-built replacement is torn down...
    new = client.containers.created[0]
    assert new.removed is True
    # ...and the original restored and restarted.
    assert old.removed is False
    assert old.renamed_to == "web"
    assert old.started is True
    assert old.labels["com.bearlike.ssm.revision"] == '"v1"'


def test_apply_rollback_leaves_stopped_original_stopped():
    # No State.Running: a discovered-but-not-running container must not be
    # spuriously started by the rollback path.
    client = FakeDockerClient(fail_create=True)
    driver = DockerDriver(client=client)
    old = FakeContainer(dict(ATTRS["Config"]["Labels"]), attrs=ATTRS)
    unit = Unit(id="c1", name="web", raw=old)

    with pytest.raises(DriverError):
        driver.apply(unit, {}, '"v2"')

    assert old.removed is False
    assert old.renamed_to == "web"
    assert old.started is False


def test_apply_backup_name_uses_id_suffix_on_collision():
    client = FakeDockerClient(fail_create=True, existing_names=("web-ssmold",))
    driver = DockerDriver(client=client)
    old = FakeContainer(dict(ATTRS["Config"]["Labels"]), attrs=ATTRS)
    unit = Unit(id="c1", name="web", raw=old)

    with pytest.raises(DriverError):
        driver.apply(unit, {}, '"v2"')

    # "web-ssmold" is taken, so the short old-id is appended for the aside
    # rename; rollback then renames back to the real name.
    assert old.renamed_to == "web"


# --- HostConfig field cloning (config-drift fix) ------------------

HOSTCFG_ATTRS: dict[str, Any] = {
    "Id": "svcid000000000000",
    "Name": "/svc",
    "Config": {"Image": "busybox"},
    "HostConfig": {
        "ExtraHosts": ["db:10.0.0.5", "cache:10.0.0.6"],
        "Devices": [
            {
                "PathOnHost": "/dev/sda",
                "PathInContainer": "/dev/xvda",
                "CgroupPermissions": "rwm",
            }
        ],
        "Ulimits": [
            {"Name": "nofile", "Soft": 1024, "Hard": 2048},
            {"Name": "nproc", "Soft": 512, "Hard": 1024},
        ],
        "Sysctls": {"net.ipv4.ip_forward": "1"},
        "Dns": ["1.1.1.1"],
        "DnsSearch": ["example.com"],
        "DnsOptions": ["ndots:2"],
        "CpuQuota": 50000,
        "CpuPeriod": 100000,
        "CpusetCpus": "0-1",
        "CpusetMems": "0",
        "MemorySwap": 1073741824,
        "BlkioWeight": 500,
        "ShmSize": 67108864,
    },
}


def test_build_spec_clones_extended_host_config_fields():
    kw = build_recreate_spec(HOSTCFG_ATTRS, {}, '"v2"').create_kwargs
    assert kw["extra_hosts"] == ["db:10.0.0.5", "cache:10.0.0.6"]
    assert kw["devices"] == ["/dev/sda:/dev/xvda:rwm"]
    assert kw["sysctls"] == {"net.ipv4.ip_forward": "1"}
    assert kw["dns"] == ["1.1.1.1"]
    assert kw["dns_search"] == ["example.com"]
    assert kw["dns_opt"] == ["ndots:2"]
    assert kw["cpu_quota"] == 50000
    assert kw["cpu_period"] == 100000
    assert kw["cpuset_cpus"] == "0-1"
    assert kw["cpuset_mems"] == "0"
    assert kw["memswap_limit"] == 1073741824
    assert kw["blkio_weight"] == 500
    assert kw["shm_size"] == 67108864


def test_typed_kwargs_wraps_ulimits_as_ulimit_objects():
    import docker

    spec = build_recreate_spec(HOSTCFG_ATTRS, {}, '"v2"')
    # The pure spec keeps raw HostConfig dicts (no docker import needed)...
    assert spec.create_kwargs["ulimits"] == [
        {"Name": "nofile", "Soft": 1024, "Hard": 2048},
        {"Name": "nproc", "Soft": 512, "Hard": 1024},
    ]
    # ...and _typed_kwargs wraps them into docker.types.Ulimit at apply
    # time, mirroring how Healthcheck/LogConfig are wrapped.
    ulimits = _typed_kwargs(spec.create_kwargs)["ulimits"]
    assert all(isinstance(u, docker.types.Ulimit) for u in ulimits)
    assert ulimits[0]["Name"] == "nofile"
    assert ulimits[0]["Soft"] == 1024
    assert ulimits[0]["Hard"] == 2048


def test_build_spec_omits_absent_host_config_fields():
    kw = build_recreate_spec(ATTRS, {}, '"v2"').create_kwargs
    for absent in (
        "extra_hosts",
        "devices",
        "ulimits",
        "sysctls",
        "dns",
        "dns_search",
        "dns_opt",
        "cpu_quota",
        "cpu_period",
        "cpuset_cpus",
        "memswap_limit",
        "blkio_weight",
        "shm_size",
    ):
        assert absent not in kw


# --- discovery: the lifecycle facts that gate a recreate ----------


def _created_at(seconds_ago: float) -> str:
    stamp = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    # Docker reports RFC3339 with NANOsecond precision, which
    # datetime.fromisoformat cannot parse -- keep the real shape here.
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.") + "123456789Z"


def _managed_container(
    container_id: str,
    name: str,
    *,
    labels: dict[str, str] | None = None,
    status: str = "running",
    age: float = 3600.0,
    network_mode: str = "bridge",
) -> FakeContainer:
    merged = {
        ENABLE_LABEL: "true",
        "com.bearlike.ssm.config": "vpn/zurich",
        **(labels or {}),
    }
    return FakeContainer(
        merged,
        attrs={
            "Id": container_id,
            "Name": f"/{name}",
            "Created": _created_at(age),
            "State": {"Status": status, "Running": status == "running"},
            "Config": {"Image": "img", "Env": [], "Labels": merged},
            "HostConfig": {"NetworkMode": network_mode},
        },
    )


def test_discover_reads_the_external_owner_from_the_compose_label():
    owned = _managed_container(
        "c1",
        "vpn-gluetun-1",
        labels={"com.docker.compose.project": "vpn-stremio"},
    )
    driver = DockerDriver(client=FakeDockerClient(listed=(owned,)))

    unit = driver.discover()[0]

    # A compose project label means compose created it -- SSM is NOT its
    # lifecycle owner and must not recreate it.
    assert unit.lifecycle.owner == "vpn-stremio"


def test_discover_reports_status_and_age_for_the_settling_window():
    fresh = _managed_container("c1", "web", status="created", age=2.0)
    driver = DockerDriver(client=FakeDockerClient(listed=(fresh,)))

    unit = driver.discover()[0]

    assert unit.lifecycle.status == "created"
    assert unit.lifecycle.age_seconds is not None
    assert 0 <= unit.lifecycle.age_seconds < 60


def test_discover_detects_containers_sharing_our_network_namespace():
    donor = _managed_container("gluetun-id", "vpn-gluetun-1")
    dependent = FakeContainer(
        {"com.docker.compose.project": "vpn-stremio"},
        attrs={
            "Id": "stremio-id",
            "Name": "/t-stremio-server",
            "Config": {
                "Labels": {"com.docker.compose.project": "vpn-stremio"}
            },
            # network_mode: "service:gluetun" is stored like this.
            "HostConfig": {"NetworkMode": "container:gluetun-id"},
        },
    )
    driver = DockerDriver(client=FakeDockerClient(listed=(donor, dependent)))

    unit = driver.discover()[0]

    # Recreating the donor mints a new id and leaves this container attached
    # to a DEAD namespace -- nothing detected that before.
    assert [d.name for d in unit.lifecycle.dependents] == ["t-stremio-server"]
    assert unit.lifecycle.dependents[0].id == "stremio-id"
    assert unit.lifecycle.dependents[0].owner == "vpn-stremio"


def test_read_managed_keys_reads_the_keys_label():
    driver = DockerDriver(client=object())
    container = FakeContainer({"com.bearlike.ssm.keys": "A,B"})
    unit = Unit(id="c1", name="web", raw=container)

    assert driver.read_managed_keys(unit) == {"A", "B"}


def test_read_managed_keys_is_empty_when_the_label_is_absent():
    driver = DockerDriver(client=object())
    unit = Unit(id="c1", name="web", raw=FakeContainer({}))

    assert driver.read_managed_keys(unit) == set()


# --- netns donors: converge dependents, never orphan them ---------


def test_apply_repoints_netns_dependents_at_the_recreated_donor():
    dependent = FakeContainer(
        {},
        attrs={
            "Id": "dep-id",
            "Name": "/t-stremio-server",
            "Config": {"Image": "stremio", "Env": ["TZ=UTC"], "Labels": {}},
            "State": {"Status": "running", "Running": True},
            "HostConfig": {"NetworkMode": "container:gluetun-id"},
        },
    )
    donor = _managed_container("gluetun-id", "vpn-gluetun-1")
    client = FakeDockerClient(listed=(donor, dependent))
    driver = DockerDriver(client=client)
    unit = driver.discover()[0]

    driver.apply(unit, {"WIREGUARD_DNS": "10.2.0.1"}, '"v2"')

    donor_new, dependent_new = client.containers.created
    assert donor_new.kwargs["name"] == "vpn-gluetun-1"
    # The dependent is recreated pointing at the NEW donor id, with its own
    # env untouched -- it is not an SSM-managed unit, just a passenger.
    assert dependent_new.kwargs["name"] == "t-stremio-server"
    assert dependent_new.kwargs["network_mode"] == f"container:{donor_new.id}"
    assert dependent_new.kwargs["environment"] == {"TZ": "UTC"}
    assert dependent_new.started is True
    assert dependent.removed is True


# --- the projection volume ----------------------------------------


def test_ensure_volume_creates_a_ram_backed_tmpfs_volume():
    client = FakeDockerClient()
    driver = DockerDriver(client=client)

    driver.ensure_volume("ssm-env")

    assert client.volumes.created == [
        {
            "name": "ssm-env",
            "driver": "local",
            "driver_opts": TMPFS_VOLUME_OPTS,
            "labels": {"com.bearlike.ssm.owner": "ssm-reload"},
        }
    ]
    # tmpfs is what keeps projected secrets off the host's disk.
    assert TMPFS_VOLUME_OPTS["type"] == "tmpfs"


def test_ensure_volume_is_idempotent_when_the_volume_exists():
    existing = SimpleNamespace(
        name="ssm-env",
        attrs={"Options": {"type": "tmpfs"}},
    )
    client = FakeDockerClient(volumes={"ssm-env": existing})
    driver = DockerDriver(client=client)

    driver.ensure_volume("ssm-env")

    assert client.volumes.created == []


def test_ensure_volume_warns_when_an_existing_volume_is_disk_backed(caplog):
    existing = SimpleNamespace(name="ssm-env", attrs={"Options": {}})
    client = FakeDockerClient(volumes={"ssm-env": existing})
    driver = DockerDriver(client=client)

    driver.ensure_volume("ssm-env")

    # Docker auto-creates a plain disk-backed volume on first `-v ssm-env:...`
    # use; silently writing secrets to disk there would break the promise
    # that projected secrets never touch the disk.
    assert "not tmpfs-backed" in caplog.text

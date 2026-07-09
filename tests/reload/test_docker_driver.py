from __future__ import annotations

from typing import Any

import pytest

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
            "ssm.enable": "true",
            "ssm.config": "proj/prod",
            "ssm.revision": '"v1"',
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


def test_build_spec_replaces_env_and_updates_revision():
    spec = build_recreate_spec(ATTRS, {"SECRET_NEW": "new"}, '"v2"', "ssm")
    kwargs = spec.create_kwargs
    # Environment fully REPLACED with the fresh secrets.
    assert kwargs["environment"] == {"SECRET_NEW": "new"}
    # Revision label bumped; other labels preserved.
    assert kwargs["labels"]["ssm.revision"] == '"v2"'
    assert kwargs["labels"]["com.example.team"] == "payments"
    assert kwargs["labels"]["ssm.config"] == "proj/prod"


def test_build_spec_preserves_core_runtime_fields():
    spec = build_recreate_spec(ATTRS, {}, '"v2"', "ssm")
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
    spec = build_recreate_spec(ATTRS, {}, '"v2"', "ssm")
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
    spec = build_recreate_spec(ATTRS, {}, '"v2"', "ssm")
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
    spec = build_recreate_spec(attrs, {}, '"v2"', "ssm")
    assert spec.create_kwargs["network_mode"] == "host"
    assert "network" not in spec.create_kwargs
    assert spec.networks == {}


# --- read_binding label parsing -----------------------------------


class FakeContainer:
    def __init__(self, labels: dict[str, str], attrs: Any = None) -> None:
        self.labels = labels
        self.attrs = attrs or {}
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
    driver = DockerDriver(label_prefix="ssm", client=object())
    container = FakeContainer(labels)
    return driver, Unit(id="c1", name="web", raw=container)


def test_read_binding_parses_project_config_and_revision():
    driver, unit = _driver_unit(
        {"ssm.config": "proj/prod", "ssm.revision": '"v9"'}
    )
    binding = driver.read_binding(unit)
    assert binding.project == "proj"
    assert binding.config == "prod"
    assert binding.held_revision == '"v9"'


def test_read_binding_missing_revision_is_none():
    driver, unit = _driver_unit({"ssm.config": "proj/prod"})
    binding = driver.read_binding(unit)
    assert binding.held_revision is None


@pytest.mark.parametrize(
    "labels",
    [
        {},
        {"ssm.config": "noslash"},
        {"ssm.config": "/prod"},
        {"ssm.config": "proj/"},
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
        self, kwargs: dict[str, Any], *, fail_start: bool = False
    ) -> None:
        self.kwargs = kwargs
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
    ) -> None:
        self.created: list[FakeNewContainer] = []
        self._fail_create = fail_create
        self._fail_start = fail_start
        self._existing = set(existing_names)

    def create(self, **kwargs: Any) -> FakeNewContainer:
        if self._fail_create:
            raise RuntimeError("create boom")
        new = FakeNewContainer(kwargs, fail_start=self._fail_start)
        self.created.append(new)
        return new

    def get(self, name: str) -> Any:
        if name in self._existing:
            return object()
        raise KeyError(name)


class FakeNetworksApi:
    def __init__(self) -> None:
        self.nets: dict[str, FakeNetwork] = {}

    def get(self, name: str) -> FakeNetwork:
        return self.nets.setdefault(name, FakeNetwork(name))


class FakeDockerClient:
    def __init__(
        self,
        *,
        fail_create: bool = False,
        fail_start: bool = False,
        existing_names: tuple[str, ...] = (),
    ) -> None:
        self.containers = FakeContainersApi(
            fail_create=fail_create,
            fail_start=fail_start,
            existing_names=existing_names,
        )
        self.networks = FakeNetworksApi()


def test_apply_recreates_with_env_replaced_and_networks_preserved():
    client = FakeDockerClient()
    driver = DockerDriver(label_prefix="ssm", client=client)
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
    assert new.kwargs["environment"] == {"SECRET_NEW": "new"}
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
    driver = DockerDriver(label_prefix="ssm", client=client)
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
    assert old.labels["ssm.revision"] == '"v1"'


def test_apply_rolls_back_when_start_fails():
    client = FakeDockerClient(fail_start=True)
    driver = DockerDriver(label_prefix="ssm", client=client)
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
    assert old.labels["ssm.revision"] == '"v1"'


def test_apply_rollback_leaves_stopped_original_stopped():
    # No State.Running: a discovered-but-not-running container must not be
    # spuriously started by the rollback path.
    client = FakeDockerClient(fail_create=True)
    driver = DockerDriver(label_prefix="ssm", client=client)
    old = FakeContainer(dict(ATTRS["Config"]["Labels"]), attrs=ATTRS)
    unit = Unit(id="c1", name="web", raw=old)

    with pytest.raises(DriverError):
        driver.apply(unit, {}, '"v2"')

    assert old.removed is False
    assert old.renamed_to == "web"
    assert old.started is False


def test_apply_backup_name_uses_id_suffix_on_collision():
    client = FakeDockerClient(fail_create=True, existing_names=("web-ssmold",))
    driver = DockerDriver(label_prefix="ssm", client=client)
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
    kw = build_recreate_spec(HOSTCFG_ATTRS, {}, '"v2"', "ssm").create_kwargs
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

    spec = build_recreate_spec(HOSTCFG_ATTRS, {}, '"v2"', "ssm")
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
    kw = build_recreate_spec(ATTRS, {}, '"v2"', "ssm").create_kwargs
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

"""SwarmDriver: the Docker Swarm implementation of the ReloadDriver seam.

Hermetic like the rest of the suite -- the Docker SDK is faked, never
imported for real. ``_docker()`` is monkeypatched to hand back a small
namespace standing in for the ``docker`` module (``types``/``errors``),
and every service/secret is a bare object carrying just the attributes
the driver reads.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from ssm_reload.config import CONFIG_LABEL, ENABLE_LABEL, REVISION_LABEL
from ssm_reload.errors import BindingError, DriverError
from ssm_reload.models import Unit
from ssm_reload.swarm_driver import SwarmDriver, _object_name, _object_prefix


class FakeAPIError(Exception):
    def __init__(self, status_code: int | None = None) -> None:
        super().__init__("api error")
        self.response = (
            SimpleNamespace(status_code=status_code)
            if status_code is not None
            else None
        )


def _reference_cls(id_key: str, name_key: str):
    class _Reference(dict):
        def __init__(
            self, obj_id, name, filename=None, uid=None, gid=None, mode=0o444
        ):
            self[id_key] = obj_id
            self[name_key] = name
            self["File"] = {
                "Name": filename or name,
                "UID": uid or "0",
                "GID": gid or "0",
                "Mode": mode,
            }

    return _Reference


SecretReference = _reference_cls("SecretID", "SecretName")
ConfigReference = _reference_cls("ConfigID", "ConfigName")

FAKE_DOCKER = SimpleNamespace(
    types=SimpleNamespace(
        SecretReference=SecretReference, ConfigReference=ConfigReference
    ),
    errors=SimpleNamespace(APIError=FakeAPIError),
)


class FakeObject:
    def __init__(self, obj_id: str, name: str) -> None:
        self.id = obj_id
        self.name = name
        self.removed = False

    def remove(self) -> None:
        self.removed = True


class FakeObjectCollection:
    """Stands in for ``client.secrets`` / ``client.configs``."""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self._by_name: dict[str, FakeObject] = {}
        self._next_id = 0
        self.create_error: Exception | None = None

    def create(self, *, name: str, data: bytes, labels: dict[str, str]):
        if self.create_error is not None:
            raise self.create_error
        self._next_id += 1
        obj = FakeObject(f"obj-{self._next_id}", name)
        self._by_name[name] = obj
        self.created.append({"name": name, "data": data, "labels": labels})
        return obj

    def get(self, name: str):
        return self._by_name[name]

    def list(self, filters=None):
        return list(self._by_name.values())


class FakeService:
    def __init__(self, service_id: str, name: str, attrs: dict[str, Any]):
        self.id = service_id
        self.name = name
        self.attrs = attrs
        self.update_calls: list[dict[str, Any]] = []

    def update(self, **kwargs: Any) -> None:
        self.update_calls.append(kwargs)


class FakeServiceCollection:
    def __init__(self, services: list[FakeService]) -> None:
        self._services = services

    def list(self, filters=None):
        return list(self._services)


def _service_attrs(
    labels: dict[str, str],
    secrets: list[dict[str, Any]] | None = None,
    container_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "Spec": {
            "Labels": labels,
            "TaskTemplate": {
                "ContainerSpec": {
                    "Secrets": secrets or [],
                    "Configs": [],
                    "Labels": container_labels or {},
                }
            },
        },
        "UpdatedAt": "2026-01-01T00:00:00.000000000Z",
    }


def _driver(
    secrets_col=None,
    services=None,
    secret_kind="secret",
    configs_col=None,
    config_mount_dir="/run/ssm",
):
    client = SimpleNamespace(
        secrets=secrets_col or FakeObjectCollection(),
        configs=configs_col or FakeObjectCollection(),
        services=FakeServiceCollection(services or []),
    )
    return SwarmDriver(
        secret_kind=secret_kind,
        config_mount_dir=config_mount_dir,
        client=client,
    )


@pytest.fixture(autouse=True)
def _patch_docker_sdk(monkeypatch):
    monkeypatch.setattr("ssm_reload.swarm_driver._docker", lambda: FAKE_DOCKER)


def test_object_name_is_deterministic_per_revision():
    from ssm_reload.models import ConfigRef

    ref = ConfigRef("web", "prod")
    assert _object_name(ref, "v1") == _object_name(ref, "v1")
    assert _object_name(ref, "v1") != _object_name(ref, "v2")
    assert _object_name(ref, "v1").startswith(_object_prefix(ref))


def test_read_binding_parses_labels():
    driver = _driver()
    service = FakeService(
        "svc1",
        "web",
        _service_attrs(
            {
                ENABLE_LABEL: "true",
                CONFIG_LABEL: "web/prod",
                REVISION_LABEL: '"v1"',
            }
        ),
    )
    unit = Unit(id=service.id, name=service.name, raw=service)
    binding = driver.read_binding(unit)
    assert binding.project == "web"
    assert binding.config == "prod"
    assert binding.held_revision == '"v1"'


def test_read_binding_missing_label_raises():
    driver = _driver()
    service = FakeService("svc1", "web", _service_attrs({}))
    unit = Unit(id=service.id, name=service.name, raw=service)
    with pytest.raises(BindingError):
        driver.read_binding(unit)


def test_discover_finds_service_via_service_level_labels():
    # Compose's `deploy.labels`.
    service = FakeService(
        "svc1",
        "web",
        _service_attrs({ENABLE_LABEL: "true", CONFIG_LABEL: "web/prod"}),
    )
    driver = _driver(services=[service])
    units = driver.discover()
    assert [u.id for u in units] == ["svc1"]


def test_discover_finds_service_via_container_level_labels_too():
    # Compose's plain `labels:` (no `deploy:`) sets the TASK TEMPLATE's
    # container labels, not the service's own -- `docker service ls`'s
    # label filter only sees the latter, so discovery must check both.
    service = FakeService(
        "svc1",
        "web",
        _service_attrs(
            {},
            container_labels={
                ENABLE_LABEL: "true",
                CONFIG_LABEL: "web/prod",
            },
        ),
    )
    driver = _driver(services=[service])
    units = driver.discover()
    assert [u.id for u in units] == ["svc1"]


def test_discover_ignores_services_without_enable_label():
    service = FakeService(
        "svc1", "web", _service_attrs({CONFIG_LABEL: "web/prod"})
    )
    driver = _driver(services=[service])
    assert driver.discover() == []


def test_read_env_and_managed_keys_are_always_empty():
    # Secrets are delivered as a mounted file, never as literal service env,
    # so there is nothing to compare -- see swarm_driver module docstring.
    driver = _driver()
    service = FakeService(
        "svc1", "web", _service_attrs({CONFIG_LABEL: "web/prod"})
    )
    unit = Unit(id=service.id, name=service.name, raw=service)
    assert driver.read_env(unit) == {}
    assert driver.read_managed_keys(unit) == set()


def test_apply_creates_secret_and_updates_service():
    secrets_col = FakeObjectCollection()
    service = FakeService(
        "svc1",
        "web",
        _service_attrs({CONFIG_LABEL: "web/prod", ENABLE_LABEL: "true"}),
    )
    driver = _driver(secrets_col=secrets_col, services=[service])
    unit = Unit(id=service.id, name=service.name, raw=service)

    driver.apply(unit, {"A": "1", "B": "2"}, '"rev1"')

    assert len(secrets_col.created) == 1
    assert secrets_col.created[0]["name"].startswith("ssm-web-prod-")
    assert b'A="1"' in secrets_col.created[0]["data"]

    assert len(service.update_calls) == 1
    call = service.update_calls[0]
    assert call["labels"][REVISION_LABEL] == '"rev1"'
    assert len(call["secrets"]) == 1
    assert call["secrets"][0]["SecretName"] == secrets_col.created[0]["name"]
    assert call["secrets"][0]["File"]["Name"] == "web-prod.env"


def test_apply_preserves_unrelated_secret_references():
    secrets_col = FakeObjectCollection()
    other_ref = {
        "SecretID": "other-id",
        "SecretName": "unrelated-secret",
        "File": {"Name": "unrelated", "UID": "0", "GID": "0", "Mode": 292},
    }
    service = FakeService(
        "svc1",
        "web",
        _service_attrs({CONFIG_LABEL: "web/prod"}, secrets=[other_ref]),
    )
    driver = _driver(secrets_col=secrets_col, services=[service])
    unit = Unit(id=service.id, name=service.name, raw=service)

    driver.apply(unit, {"A": "1"}, '"rev1"')

    call = service.update_calls[0]
    names = {ref["SecretName"] for ref in call["secrets"]}
    assert "unrelated-secret" in names
    assert len(call["secrets"]) == 2


def test_apply_reuses_object_on_conflict():
    secrets_col = FakeObjectCollection()
    secrets_col.create_error = FakeAPIError(status_code=409)
    # Pre-seed the object the 409 branch expects to find already there.
    from ssm_reload.models import ConfigRef

    name = _object_name(ConfigRef("web", "prod"), '"rev1"')
    secrets_col._by_name[name] = FakeObject("existing-id", name)

    service = FakeService(
        "svc1", "web", _service_attrs({CONFIG_LABEL: "web/prod"})
    )
    driver = _driver(secrets_col=secrets_col, services=[service])
    unit = Unit(id=service.id, name=service.name, raw=service)

    driver.apply(unit, {"A": "1"}, '"rev1"')

    assert service.update_calls[0]["secrets"][0]["SecretID"] == "existing-id"


def test_apply_wraps_other_api_errors():
    secrets_col = FakeObjectCollection()
    secrets_col.create_error = FakeAPIError(status_code=500)
    service = FakeService(
        "svc1", "web", _service_attrs({CONFIG_LABEL: "web/prod"})
    )
    driver = _driver(secrets_col=secrets_col, services=[service])
    unit = Unit(id=service.id, name=service.name, raw=service)

    with pytest.raises(DriverError):
        driver.apply(unit, {"A": "1"}, '"rev1"')


def test_apply_mounts_config_kind_under_run_ssm():
    # Secrets are pinned to /run/secrets/<name> by Swarm itself; configs are
    # not, so they use the configurable SSM_RELOAD_SWARM_CONFIG_MOUNT_DIR.
    configs_col = FakeObjectCollection()
    service = FakeService(
        "svc1", "web", _service_attrs({CONFIG_LABEL: "web/prod"})
    )
    driver = _driver(
        services=[service], secret_kind="config", configs_col=configs_col
    )
    unit = Unit(id=service.id, name=service.name, raw=service)

    driver.apply(unit, {"A": "1"}, '"rev1"')

    call = service.update_calls[0]
    assert call["configs"][0]["File"]["Name"] == "/run/ssm/web-prod.env"


def test_apply_honors_custom_config_mount_dir():
    configs_col = FakeObjectCollection()
    service = FakeService(
        "svc1", "web", _service_attrs({CONFIG_LABEL: "web/prod"})
    )
    driver = _driver(
        services=[service],
        secret_kind="config",
        configs_col=configs_col,
        config_mount_dir="/etc/ssm",
    )
    unit = Unit(id=service.id, name=service.name, raw=service)

    driver.apply(unit, {"A": "1"}, '"rev1"')

    call = service.update_calls[0]
    assert call["configs"][0]["File"]["Name"] == "/etc/ssm/web-prod.env"


def test_apply_takes_over_a_bootstrap_secret_at_the_same_target():
    # A placeholder secret an operator pre-created for first-boot bootstrap,
    # mounted at the same target ssm-reload uses, must be REPLACED rather
    # than left attached alongside ours (Swarm rejects two refs at one
    # target anyway).
    secrets_col = FakeObjectCollection()
    placeholder = {
        "SecretID": "placeholder-id",
        "SecretName": "test-prod.env",
        "File": {
            "Name": "web-prod.env",
            "UID": "0",
            "GID": "0",
            "Mode": 292,
        },
    }
    service = FakeService(
        "svc1",
        "web",
        _service_attrs({CONFIG_LABEL: "web/prod"}, secrets=[placeholder]),
    )
    driver = _driver(secrets_col=secrets_col, services=[service])
    unit = Unit(id=service.id, name=service.name, raw=service)

    driver.apply(unit, {"A": "1"}, '"rev1"')

    call = service.update_calls[0]
    assert len(call["secrets"]) == 1
    assert call["secrets"][0]["SecretID"] != "placeholder-id"


def test_gc_removes_only_unreferenced_owned_objects():
    secrets_col = FakeObjectCollection()
    kept = secrets_col.create(name="ssm-web-prod-aaa", data=b"", labels={})
    orphan = secrets_col.create(name="ssm-web-prod-bbb", data=b"", labels={})

    service = FakeService(
        "svc1",
        "web",
        _service_attrs(
            {CONFIG_LABEL: "web/prod"},
            secrets=[
                {
                    "SecretID": kept.id,
                    "SecretName": kept.name,
                    "File": {
                        "Name": "web-prod.env",
                        "UID": "0",
                        "GID": "0",
                        "Mode": 292,
                    },
                }
            ],
        ),
    )
    driver = _driver(secrets_col=secrets_col, services=[service])

    driver.gc()

    assert kept.removed is False
    assert orphan.removed is True

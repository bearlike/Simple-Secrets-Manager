"""Docker implementation of the :class:`ReloadDriver` seam.

The interesting part is :func:`build_recreate_spec`: a *pure* function
that maps a container's ``attrs`` (the ``docker inspect`` payload) into
the keyword arguments needed to recreate it with an identical runtime
spec -- same image, entrypoint/command, working dir, user, mounts,
networks (with their aliases), published ports, restart policy,
healthcheck, log config, resource limits, and labels -- while REPLACING
its environment and stamping a fresh ``ssm.revision`` label. It has no
Docker dependency so it can be unit-tested directly. ``docker`` is
imported lazily so importing this module never requires the SDK.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ssm_reload.errors import BindingError, DriverError
from ssm_reload.models import Binding, Unit

logger = logging.getLogger("ssm_reload.docker_driver")


def _docker() -> Any:
    """Import the docker SDK lazily, typed as ``Any``.

    The SDK ships only with the ``reload`` extra, so importing this
    module (and unit-testing the pure ``build_recreate_spec``) never
    requires it; the ``Any``-typed shim also keeps the type checker happy
    without leaking the workaround across the module. A missing SDK is
    surfaced as a clean, actionable :class:`DriverError` rather than a raw
    ``ModuleNotFoundError`` traceback (matching the no-traceback contract).
    """
    try:
        import docker
    except ModuleNotFoundError as exc:
        raise DriverError(
            "The Docker SDK is required to run ssm-reload but is not "
            "installed. Install the reload extra: "
            "pip install 'simple-secrets-manager[reload]'"
        ) from exc

    return docker


def require_docker_sdk() -> None:
    """Fail fast if the Docker SDK (the ``reload`` extra) is missing.

    Called at start-up so a base-only install exits with a single clean
    hint instead of spinning in the reconcile loop logging the same
    skip warning every poll interval.
    """
    _docker()


@dataclass
class RecreateSpec:
    """Recreate instructions derived from a container's ``attrs``."""

    create_kwargs: dict[str, Any]
    networks: dict[str, dict[str, Any]] = field(default_factory=dict)
    primary_network: str | None = None


class DockerDriver:
    """Manage local Docker containers opted in with ``ssm.enable=true``."""

    def __init__(
        self,
        *,
        label_prefix: str = "ssm",
        docker_host: str | None = None,
        client: Any = None,
    ) -> None:
        self.label_prefix = label_prefix
        self._client = client
        self._docker_host = docker_host

    @property
    def client(self) -> Any:
        if self._client is None:
            docker = _docker()
            self._client = (
                docker.DockerClient(base_url=self._docker_host)
                if self._docker_host
                else docker.from_env()
            )
        return self._client

    @property
    def enable_label(self) -> str:
        return f"{self.label_prefix}.enable"

    def discover(self) -> list[Unit]:
        containers = self.client.containers.list(
            filters={"label": f"{self.enable_label}=true"}
        )
        return [Unit(id=c.id, name=c.name, raw=c) for c in containers]

    def read_binding(self, unit: Unit) -> Binding:
        labels = _labels_of(unit.raw)
        config_label = labels.get(f"{self.label_prefix}.config")
        if not config_label or "/" not in config_label:
            raise BindingError(
                f"{unit.name}: missing or malformed "
                f"'{self.label_prefix}.config' label"
            )
        project, _, config = config_label.partition("/")
        if not project or not config:
            raise BindingError(
                f"{unit.name}: '{self.label_prefix}.config' must be "
                "'project/config'"
            )
        revision = labels.get(f"{self.label_prefix}.revision") or None
        return Binding(project=project, config=config, held_revision=revision)

    def apply(self, unit: Unit, env: dict[str, str], revision: str) -> None:
        """Recreate ``unit`` non-destructively, rolling back on failure.

        The ORIGINAL container is never destroyed until the replacement
        has been created AND started. It is stopped and renamed aside to
        a backup name first; if creating/attaching/starting the new
        container raises, the half-built replacement is removed, the
        backup is renamed back to the original name and (if it had been
        running) restarted, and a :class:`DriverError` is raised. Because
        the original keeps its OLD ``ssm.revision`` label throughout, a
        failed recreate leaves the unit DIVERGENT -- so ``reconcile``
        logs it, never reports it, and retries it next pass -- instead of
        stamping a broken container as up to date.
        """
        container = unit.raw
        attrs = container.attrs or {}
        original_name = (attrs.get("Name") or unit.name or "").lstrip("/")
        was_running = bool((attrs.get("State") or {}).get("Running"))
        old_id = (attrs.get("Id") or "")[:12]

        spec = self._build_spec(unit, attrs, env, revision)
        backup_name = self._pick_backup_name(original_name, old_id)
        self._stop_and_set_aside(unit, container, backup_name, was_running)

        new_container = None
        try:
            new_container = self.client.containers.create(
                **_typed_kwargs(spec.create_kwargs)
            )
            _attach_networks(self.client, new_container, spec)
            new_container.start()
        except Exception as exc:  # roll back: the workload is never lost.
            self._rollback(
                container, new_container, original_name, was_running
            )
            raise DriverError(f"{unit.name}: recreate failed: {exc}") from exc

        self._discard_backup(unit, container)

    def _build_spec(
        self,
        unit: Unit,
        attrs: dict[str, Any],
        env: dict[str, str],
        revision: str,
    ) -> RecreateSpec:
        try:
            return build_recreate_spec(attrs, env, revision, self.label_prefix)
        except DriverError:
            raise
        except Exception as exc:  # normalize any mapping error.
            raise DriverError(f"{unit.name}: recreate failed: {exc}") from exc

    def _pick_backup_name(self, original_name: str, old_id: str) -> str:
        """Pick a free ``-ssmold`` backup name for the aside rename.

        Two consecutive failed recreates could otherwise collide on the
        same ``-ssmold`` name, so fall back to a short old-id suffix when
        the plain name is already taken.
        """
        candidate = f"{original_name}-ssmold"
        if old_id and not self._name_available(candidate):
            candidate = f"{candidate}-{old_id}"
        return candidate

    def _name_available(self, name: str) -> bool:
        """Best-effort check that no container already owns ``name``."""
        try:
            self.client.containers.get(name)
        except Exception:
            return True
        return False

    def _stop_and_set_aside(
        self,
        unit: Unit,
        container: Any,
        backup_name: str,
        was_running: bool,
    ) -> None:
        """Stop the original and rename it aside as the rollback anchor."""
        try:
            container.stop()
        except Exception as exc:
            raise DriverError(f"{unit.name}: recreate failed: {exc}") from exc
        try:
            container.rename(backup_name)
        except Exception as exc:
            # Nothing new exists yet; a rename hiccup must not leave a
            # healthy workload down -- put it back up if it was up.
            if was_running:
                self._best_effort_start(unit.name, container)
            raise DriverError(f"{unit.name}: recreate failed: {exc}") from exc

    def _rollback(
        self,
        backup: Any,
        new_container: Any,
        original_name: str,
        was_running: bool,
    ) -> None:
        """Undo a failed recreate, restoring the original container.

        Removes the half-built replacement first (freeing the original
        name), then renames the backup back and restarts it if it had
        been running. Every step is best-effort so rollback never masks
        the original failure with a second exception.
        """
        if new_container is not None:
            try:
                new_container.remove(force=True)
            except Exception as exc:
                logger.warning(
                    "Rollback: failed to remove new container: %s", exc
                )
        try:
            backup.rename(original_name)
        except Exception as exc:
            logger.error(
                "Rollback: failed to restore name %s: %s",
                original_name,
                exc,
            )
        if was_running:
            self._best_effort_start(original_name, backup)

    def _best_effort_start(self, name: str, container: Any) -> None:
        try:
            container.start()
        except Exception as exc:
            logger.error(
                "Rollback: failed to restart original %s: %s", name, exc
            )

    def _discard_backup(self, unit: Unit, backup: Any) -> None:
        """Remove the renamed original after a successful recreate.

        Best-effort: the replacement is already running, so a cleanup
        failure must not turn a successful reload into a reported error
        (which would also leave a lingering ``-ssmold`` container behind).
        """
        try:
            backup.remove()
        except Exception as exc:
            logger.warning(
                "Recreated %s but failed to remove backup: %s",
                unit.name,
                exc,
            )


def build_recreate_spec(
    attrs: dict[str, Any],
    env: dict[str, str],
    revision: str,
    label_prefix: str,
) -> RecreateSpec:
    """Map inspect ``attrs`` to recreate kwargs (pure, no Docker import)."""
    config = attrs.get("Config") or {}
    host = attrs.get("HostConfig") or {}
    name = (attrs.get("Name") or "").lstrip("/")
    old_id = (attrs.get("Id") or "")[:12]

    kwargs: dict[str, Any] = {
        "image": config.get("Image"),
        "name": name,
        "environment": dict(env),  # REPLACED with the fresh secrets.
        "labels": _build_labels(config.get("Labels"), label_prefix, revision),
    }
    kwargs.update(_config_kwargs(config))
    kwargs.update(_host_kwargs(host))
    volumes = _build_volumes(attrs.get("Mounts"))
    if volumes:
        kwargs["volumes"] = volumes

    networks, primary, net_mode = _resolve_networking(host, attrs, old_id)
    if net_mode is not None:
        kwargs["network_mode"] = net_mode
    elif primary is not None:
        kwargs["network"] = primary

    return RecreateSpec(
        create_kwargs=kwargs,
        networks=networks,
        primary_network=primary,
    )


def _config_kwargs(config: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for src, dst in (
        ("Cmd", "command"),
        ("Entrypoint", "entrypoint"),
        ("WorkingDir", "working_dir"),
        ("User", "user"),
        ("Healthcheck", "healthcheck"),
    ):
        value = config.get(src)
        if value:
            out[dst] = value
    return out


def _host_kwargs(host: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    restart = host.get("RestartPolicy")
    if isinstance(restart, dict) and restart.get("Name"):
        out["restart_policy"] = restart
    ports = _build_ports(host.get("PortBindings"))
    if ports:
        out["ports"] = ports
    log_config = host.get("LogConfig")
    if isinstance(log_config, dict) and log_config.get("Type"):
        out["log_config"] = log_config
    out.update(_resource_kwargs(host))
    out.update(_runtime_kwargs(host))
    for src, dst in (("CapAdd", "cap_add"), ("CapDrop", "cap_drop")):
        value = host.get(src)
        if value:
            out[dst] = value
    if host.get("Privileged"):
        out["privileged"] = True
    return out


def _resource_kwargs(host: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for src, dst in (
        ("Memory", "mem_limit"),
        ("NanoCpus", "nano_cpus"),
        ("CpuShares", "cpu_shares"),
        ("CpuQuota", "cpu_quota"),
        ("CpuPeriod", "cpu_period"),
        ("CpusetCpus", "cpuset_cpus"),
        ("CpusetMems", "cpuset_mems"),
        ("MemorySwap", "memswap_limit"),
        ("BlkioWeight", "blkio_weight"),
        ("ShmSize", "shm_size"),
    ):
        value = host.get(src)
        if value:
            out[dst] = value
    return out


def _runtime_kwargs(host: dict[str, Any]) -> dict[str, Any]:
    """Clone DNS / host-mapping / device / sysctl / ulimit settings.

    These were previously dropped, so each recreate derived from an
    already-degraded live container -- cumulative config drift. Values
    that map straight through (already in docker-py's expected shape) go
    via the loop; ``Devices`` and ``Ulimits`` need format conversion.
    ``Ulimits`` stays a list of raw ``{Name,Soft,Hard}`` dicts here and
    is wrapped in ``docker.types.Ulimit`` by :func:`_typed_kwargs`, the
    same way ``Healthcheck``/``LogConfig`` are typed at apply time.
    """
    out: dict[str, Any] = {}
    for src, dst in (
        ("ExtraHosts", "extra_hosts"),  # ["host:ip"] passes through.
        ("Sysctls", "sysctls"),
        ("Dns", "dns"),
        ("DnsSearch", "dns_search"),
        ("DnsOptions", "dns_opt"),
    ):
        value = host.get(src)
        if value:
            out[dst] = value
    devices = _build_devices(host.get("Devices"))
    if devices:
        out["devices"] = devices
    ulimits = host.get("Ulimits")
    if ulimits:
        out["ulimits"] = ulimits
    return out


def _build_devices(devices: list[dict[str, Any]] | None) -> list[str]:
    """Map inspect ``Devices`` dicts to docker-py's string form."""
    out: list[str] = []
    for dev in devices or []:
        path = dev.get("PathOnHost")
        if not path:
            continue
        container_path = dev.get("PathInContainer") or path
        perms = dev.get("CgroupPermissions") or "rwm"
        out.append(f"{path}:{container_path}:{perms}")
    return out


def _build_labels(
    labels: dict[str, str] | None, prefix: str, revision: str
) -> dict[str, str]:
    merged = dict(labels or {})
    merged[f"{prefix}.revision"] = revision
    return merged


def _build_volumes(
    mounts: list[dict[str, Any]] | None,
) -> dict[str, dict[str, str]]:
    volumes: dict[str, dict[str, str]] = {}
    for mount in mounts or []:
        source = mount.get("Name") or mount.get("Source")
        destination = mount.get("Destination")
        if not source or not destination:
            continue
        mode = "rw" if mount.get("RW", True) else "ro"
        volumes[source] = {"bind": destination, "mode": mode}
    return volumes


def _build_ports(
    port_bindings: dict[str, Any] | None,
) -> dict[str, Any]:
    ports: dict[str, Any] = {}
    for port, bindings in (port_bindings or {}).items():
        values = [_one_binding(b) for b in (bindings or [])]
        if not values:
            ports[port] = None
        elif len(values) == 1:
            ports[port] = values[0]
        else:
            ports[port] = values
    return ports


def _one_binding(binding: dict[str, Any]) -> Any:
    raw_port = binding.get("HostPort")
    host_port = int(raw_port) if raw_port else None
    host_ip = binding.get("HostIp")
    if host_ip:
        return (host_ip, host_port)
    return host_port


def _resolve_networking(
    host: dict[str, Any], attrs: dict[str, Any], old_id: str
) -> tuple[dict[str, dict[str, Any]], str | None, str | None]:
    """Return ``(networks, primary_network, network_mode)``.

    Special modes (``host``/``none``/``container:*``) are passed through
    as ``network_mode`` and carry no attachable networks.
    """
    mode = host.get("NetworkMode") or ""
    if mode in ("host", "none") or mode.startswith("container:"):
        return ({}, None, mode)

    settings = (attrs.get("NetworkSettings") or {}).get("Networks") or {}
    networks: dict[str, dict[str, Any]] = {}
    for net_name, endpoint in settings.items():
        networks[net_name] = _endpoint_config(endpoint, old_id)
    primary = next(iter(networks), None)
    return (networks, primary, None)


def _endpoint_config(endpoint: dict[str, Any], old_id: str) -> dict[str, Any]:
    aliases = [
        alias
        for alias in (endpoint.get("Aliases") or [])
        if alias and alias != old_id
    ]
    out: dict[str, Any] = {}
    if aliases:
        out["aliases"] = aliases
    ipam = endpoint.get("IPAMConfig") or {}
    ipv4 = ipam.get("IPv4Address")
    if ipv4:
        out["ipv4_address"] = ipv4
    return out


def _typed_kwargs(create_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Wrap dict-valued kwargs in the docker SDK's typed helpers."""
    docker = _docker()
    out = dict(create_kwargs)
    healthcheck = out.get("healthcheck")
    if isinstance(healthcheck, dict):
        out["healthcheck"] = docker.types.Healthcheck(
            test=healthcheck.get("Test"),
            interval=healthcheck.get("Interval"),
            timeout=healthcheck.get("Timeout"),
            retries=healthcheck.get("Retries"),
            start_period=healthcheck.get("StartPeriod"),
        )
    log_config = out.get("log_config")
    if isinstance(log_config, dict):
        out["log_config"] = docker.types.LogConfig(
            type=log_config.get("Type"),
            config=log_config.get("Config") or {},
        )
    ulimits = out.get("ulimits")
    if isinstance(ulimits, list):
        # Inspect uses Name/Soft/Hard; docker-py's Ulimit(**dict) would
        # choke on those capitalized keys, so remap explicitly.
        out["ulimits"] = [
            docker.types.Ulimit(
                name=u.get("Name"),
                soft=u.get("Soft"),
                hard=u.get("Hard"),
            )
            for u in ulimits
            if isinstance(u, dict)
        ]
    return out


def _attach_networks(
    client: Any,
    container: Any,
    spec: RecreateSpec,
) -> None:
    """Connect additional networks and restore aliases on the primary."""
    for net_name, endpoint in spec.networks.items():
        network = client.networks.get(net_name)
        if net_name == spec.primary_network:
            if endpoint:  # aliases/ip need a disconnect+reconnect.
                network.disconnect(container)
                network.connect(container, **endpoint)
        else:
            network.connect(container, **endpoint)


def _labels_of(container: Any) -> dict[str, str]:
    labels = getattr(container, "labels", None)
    if isinstance(labels, dict):
        return labels
    attrs = getattr(container, "attrs", None) or {}
    config = attrs.get("Config") or {}
    return config.get("Labels") or {}

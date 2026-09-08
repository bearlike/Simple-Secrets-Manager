"""Docker implementation of the :class:`ReloadDriver` seam.

The interesting part is :func:`build_recreate_spec`: a *pure* function
that maps a container's ``attrs`` (the ``docker inspect`` payload) into
the keyword arguments needed to recreate it with an identical runtime
spec -- same image, entrypoint/command, working dir, user, mounts,
networks (with their aliases), published ports, restart policy,
healthcheck, log config, resource limits, and labels -- while MERGING
fresh secrets into its environment and stamping a fresh revision label
(the fixed ``com.bearlike.ssm`` namespace). It has no
Docker dependency so it can be unit-tested directly. ``docker`` is
imported lazily so importing this module never requires the SDK.

:meth:`DockerDriver.discover` also reads the *lifecycle* facts that decide
whether a container may be recreated at all: who else owns it, whether it
has finished being deployed, and which other containers are living inside
its network namespace.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

from ssm_reload.config import (
    CONFIG_LABEL,
    ENABLE_LABEL,
    EXTERNAL_OWNER_LABELS,
    KEYS_LABEL,
    OWNER_LABEL,
    REVISION_LABEL,
    TMPFS_VOLUME_OPTS,
)
from ssm_reload.errors import BindingError, DriverError
from ssm_reload.models import (
    Binding,
    ConfigRef,
    Dependent,
    Lifecycle,
    Unit,
)

logger = logging.getLogger("ssm_reload.docker_driver")

# Docker reports creation timestamps in RFC3339 with NANOsecond precision
# ("2026-07-14T11:11:11.123456789Z"), which datetime.fromisoformat cannot
# parse -- it accepts at most microseconds. Trim the fraction rather than
# hand-rolling a parser.
_NANOS = re.compile(r"(\.\d{6})\d+")
_NETNS_PREFIX = "container:"


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
    """Manage local Docker containers opted in via ``<prefix>.enable=true``."""

    # What the event stream watches to adopt a new/redeployed unit fast.
    EVENT_TYPE = "container"
    EVENT_ACTIONS = ["start", "create"]

    def __init__(self, *, client: Any = None) -> None:
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            # from_env() honors DOCKER_HOST/TLS settings natively — the
            # SDK owns that configuration surface, not this service.
            self._client = _docker().from_env()
        return self._client

    def discover(self) -> list[Unit]:
        containers = self.client.containers.list(
            filters={"label": f"{ENABLE_LABEL}=true"}
        )
        if not containers:
            return []
        dependents = self._dependents_by_donor()
        now = datetime.now(timezone.utc)
        return [
            Unit(
                id=c.id,
                name=c.name,
                raw=c,
                lifecycle=self._lifecycle(c, dependents, now),
            )
            for c in containers
        ]

    def ensure_volume(self, name: str) -> None:
        """Create the RAM-backed projection volume if it is missing.

        Idempotent and best-effort: the reloader mounts this volume itself,
        so by the time it runs the volume normally exists already. What this
        catches is the case that silently breaks the security promise -- a
        plain ``docker run -v ssm-env:/run/ssm`` auto-creates a DISK-backed
        volume, and projected secrets would land on the host's disk. Then we
        say so rather than pretending.
        """
        try:
            existing = self.client.volumes.get(name)
        except Exception:
            existing = None

        if existing is not None:
            options = (existing.attrs or {}).get("Options") or {}
            if options.get("type") != "tmpfs":
                logger.warning(
                    "Projection volume %s exists but is not tmpfs-backed: "
                    "projected secrets will be written to the host's disk. "
                    "Recreate it with: docker volume create --driver local "
                    "--opt type=tmpfs --opt device=tmpfs "
                    "--opt o=size=8m,mode=0750 %s",
                    name,
                    name,
                )
            return

        try:
            self.client.volumes.create(
                name=name,
                driver="local",
                driver_opts=dict(TMPFS_VOLUME_OPTS),
                labels={OWNER_LABEL: "ssm-reload"},
            )
        except Exception as exc:  # never fatal: projection is best-effort.
            logger.warning("Could not create volume %s: %s", name, exc)
            return
        logger.info("Created RAM-backed projection volume %s", name)

    def _dependents_by_donor(self) -> dict[str, list[Dependent]]:
        """Map each netns donor to the containers living inside it.

        ``network_mode: "service:gluetun"`` is stored as
        ``NetworkMode: container:<id>``. Every recreate mints a NEW id, so
        without this map a recreate silently leaves those containers
        attached to a namespace that no longer exists.
        """
        donors: dict[str, list[Dependent]] = {}
        try:
            containers = self.client.containers.list(all=True)
        except Exception as exc:
            # Fail safe: an unreadable container list means "cannot verify",
            # and reconcile refuses to recreate a unit it cannot vouch for.
            logger.warning("Could not list containers: %s", exc)
            return donors

        for container in containers:
            attrs = getattr(container, "attrs", None) or {}
            mode = (attrs.get("HostConfig") or {}).get("NetworkMode") or ""
            if not mode.startswith(_NETNS_PREFIX):
                continue
            donor_id = mode[len(_NETNS_PREFIX) :]
            labels = _labels_of(container)
            donors.setdefault(donor_id, []).append(
                Dependent(
                    id=str(getattr(container, "id", "")),
                    name=_name_of(container, attrs),
                    owner=_external_owner(labels),
                )
            )
        return donors

    def _lifecycle(
        self,
        container: Any,
        dependents: dict[str, list[Dependent]],
        now: datetime,
    ) -> Lifecycle:
        attrs = getattr(container, "attrs", None) or {}
        state = attrs.get("State") or {}
        container_id = str(getattr(container, "id", "") or "")
        # NetworkMode may name the donor by full id, short id or name
        # depending on how the dependent was created; dedupe the lookup keys
        # so a donor whose id IS its short id isn't matched twice.
        keys = {container_id, container_id[:12], container.name} - {""}
        found: list[Dependent] = []
        for key in keys:
            found.extend(dependents.get(key, ()))
        return Lifecycle(
            owner=_external_owner(_labels_of(container)),
            status=str(state.get("Status") or "running"),
            age_seconds=_age_seconds(attrs.get("Created"), now),
            dependents=tuple(found),
        )

    def read_managed_keys(self, unit: Unit) -> set[str]:
        """Key names SSM injected the last time it recreated ``unit``.

        Empty for a container SSM has never recreated (an externally-owned
        one, say), which is exactly right: SSM must not claim to manage keys
        it did not put there.
        """
        raw = _labels_of(unit.raw).get(KEYS_LABEL) or ""
        return {key.strip() for key in raw.split(",") if key.strip()}

    def read_binding(self, unit: Unit) -> Binding:
        labels = _labels_of(unit.raw)
        config_label = labels.get(CONFIG_LABEL)
        if not config_label:
            raise BindingError(f"{unit.name}: missing '{CONFIG_LABEL}' label")
        try:
            # ConfigRef owns the shape. Rejecting a non-slug HERE, at the
            # boundary, is what stops a value like "MyApp/prod" from
            # surviving into the cycle report and failing validation there,
            # which would abort the whole pass.
            ref = ConfigRef.parse(config_label)
        except BindingError as exc:
            raise BindingError(f"{unit.name}: {CONFIG_LABEL} {exc}") from exc
        return Binding(
            project=ref.project,
            config=ref.config,
            held_revision=labels.get(REVISION_LABEL) or None,
        )

    def read_env(self, unit: Unit) -> dict[str, str]:
        """Return the unit's actual environment from its inspect data.

        Reads ``Config.Env`` off the attrs docker-py already loaded
        (``containers.list`` inspects each container -- the same data
        ``apply``/``build_recreate_spec`` trust). Entries split on the
        FIRST ``=`` only, so values containing ``=`` survive intact; a
        bare ``KEY`` entry reads as an empty string.
        """
        try:
            attrs = unit.raw.attrs or {}
            raw_env = (attrs.get("Config") or {}).get("Env") or []
            env: dict[str, str] = {}
            for entry in raw_env:
                key, _sep, value = entry.partition("=")
                env[key] = value
            return env
        except Exception as exc:
            raise DriverError(f"{unit.name}: cannot read env: {exc}") from exc

    def apply(self, unit: Unit, env: dict[str, str], revision: str) -> None:
        """Recreate ``unit`` non-destructively, rolling back on failure.

        The ORIGINAL container is never destroyed until the replacement
        has been created AND started. It is stopped and renamed aside to
        a backup name first; if creating/attaching/starting the new
        container raises, the half-built replacement is removed, the
        backup is renamed back to the original name and (if it had been
        running) restarted, and a :class:`DriverError` is raised. Because
        the original keeps its OLD ``<prefix>.revision`` label throughout, a
        failed recreate leaves the unit DIVERGENT -- so ``reconcile``
        logs it, never reports it, and retries it next pass -- instead of
        stamping a broken container as up to date.

        Any container sharing this one's network namespace is carried across
        to the new namespace afterwards (``reconcile`` has already refused
        the whole recreate if one of them belongs to another owner), because
        the recreate mints a new container id and their old namespace ceases
        to exist.
        """
        container = unit.raw
        attrs = container.attrs or {}

        spec = self._build_spec(unit, attrs, env, revision)
        new_container = self._recreate(unit.name, container, attrs, spec)
        self._converge_dependents(unit, new_container)

    def _recreate(
        self,
        label: str,
        container: Any,
        attrs: dict[str, Any],
        spec: RecreateSpec,
    ) -> Any:
        """Swap ``container`` for one built from ``spec``; roll back on error.

        Shared by the managed unit and by any netns passenger that has to be
        re-pointed at its new donor -- both need the same never-lose-the-
        workload dance.
        """
        original_name = (attrs.get("Name") or label or "").lstrip("/")
        was_running = bool((attrs.get("State") or {}).get("Running"))
        old_id = (attrs.get("Id") or "")[:12]

        backup_name = self._pick_backup_name(original_name, old_id)
        self._stop_and_set_aside(label, container, backup_name, was_running)

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
            raise DriverError(f"{label}: recreate failed: {exc}") from exc

        self._discard_backup(label, container)
        return new_container

    def _converge_dependents(self, unit: Unit, donor: Any) -> None:
        """Re-point every netns passenger at the donor's new namespace."""
        dependents = unit.lifecycle.dependents
        if not dependents:
            return
        network_mode = f"{_NETNS_PREFIX}{donor.id}"
        for dependent in dependents:
            try:
                self._repoint(dependent, network_mode)
            except Exception as exc:
                # The donor is already running with fresh secrets; the
                # passenger is not. Say exactly which one, loudly: reconcile
                # turns this into a "failed" unit in the fleet view.
                raise DriverError(
                    f"{unit.name}: recreated, but its network-namespace "
                    f"dependent {dependent.name} could not follow it: {exc}"
                ) from exc

    def _repoint(self, dependent: Dependent, network_mode: str) -> None:
        container = self.client.containers.get(dependent.id)
        attrs = container.attrs or {}
        # No secrets and no revision: this container is a passenger, not a
        # managed unit. Its env and labels must come out exactly as they
        # went in -- only its namespace pointer changes.
        spec = build_recreate_spec(attrs, {}, None, network_mode=network_mode)
        self._recreate(dependent.name, container, attrs, spec)
        logger.info(
            "Re-pointed %s at the new network namespace (%s)",
            dependent.name,
            network_mode,
        )

    def _build_spec(
        self,
        unit: Unit,
        attrs: dict[str, Any],
        env: dict[str, str],
        revision: str,
    ) -> RecreateSpec:
        try:
            return build_recreate_spec(
                attrs,
                env,
                revision,
                image_env=self._image_env(attrs),
            )
        except DriverError:
            raise
        except Exception as exc:  # normalize any mapping error.
            raise DriverError(f"{unit.name}: recreate failed: {exc}") from exc

    def _image_env(self, attrs: dict[str, Any]) -> Sequence[str]:
        """The env the container's IMAGE already provides, if readable.

        Env the image supplies is not the container's own configuration:
        copying it into the recreate spec would pin the image's CURRENT
        defaults into the container forever, so a later image upgrade that
        changes one could never reach it. Best-effort -- an unreadable image
        just means we keep everything, which is what the code did before.
        """
        image = (attrs.get("Config") or {}).get("Image")
        if not image:
            return ()
        try:
            info = self.client.images.get(image)
            return list((info.attrs.get("Config") or {}).get("Env") or [])
        except Exception:
            return ()

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
        label: str,
        container: Any,
        backup_name: str,
        was_running: bool,
    ) -> None:
        """Stop the original and rename it aside as the rollback anchor."""
        try:
            container.stop()
        except Exception as exc:
            raise DriverError(f"{label}: recreate failed: {exc}") from exc
        try:
            container.rename(backup_name)
        except Exception as exc:
            # Nothing new exists yet; a rename hiccup must not leave a
            # healthy workload down -- put it back up if it was up.
            if was_running:
                self._best_effort_start(label, container)
            raise DriverError(f"{label}: recreate failed: {exc}") from exc

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

    def _discard_backup(self, label: str, backup: Any) -> None:
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
                label,
                exc,
            )


def build_recreate_spec(
    attrs: dict[str, Any],
    env: dict[str, str],
    revision: str | None,
    *,
    image_env: Sequence[str] = (),
    network_mode: str | None = None,
) -> RecreateSpec:
    """Map inspect ``attrs`` to recreate kwargs (pure, no Docker import).

    Args:
        attrs: the container's ``docker inspect`` payload.
        env: the config's freshly exported secrets, MERGED over the
            container's own environment -- never replacing it. Replacing was
            the original defect: every variable a container got from its
            compose file but which the SSM config did not carry was dropped
            on recreate, and the workload came back up broken.
        revision: the ETag to stamp, or ``None`` to leave the labels exactly
            as they are (used when re-pointing a container SSM does not
            manage at a new network namespace).
        image_env: env the container's image already provides; entries the
            container merely inherited are left to the image rather than
            frozen into the new container's own configuration.
        network_mode: overrides the cloned network mode -- how a netns
            passenger is re-pointed at its donor's new namespace.
    """
    config = attrs.get("Config") or {}
    host = attrs.get("HostConfig") or {}
    labels = config.get("Labels") or {}
    name = (attrs.get("Name") or "").lstrip("/")
    old_id = (attrs.get("Id") or "")[:12]

    kwargs: dict[str, Any] = {
        "image": config.get("Image"),
        "name": name,
        "environment": _merge_env(
            config.get("Env"),
            env,
            previously_injected=_split_keys(labels.get(KEYS_LABEL)),
            image_env=image_env,
        ),
        "labels": _build_labels(labels, revision, env),
    }
    kwargs.update(_config_kwargs(config))
    kwargs.update(_host_kwargs(host))
    volumes = _build_volumes(attrs.get("Mounts"))
    if volumes:
        kwargs["volumes"] = volumes

    networks, primary, net_mode = _resolve_networking(host, attrs, old_id)
    if network_mode is not None:
        kwargs["network_mode"] = network_mode
    elif net_mode is not None:
        kwargs["network_mode"] = net_mode
    elif primary is not None:
        kwargs["network"] = primary

    return RecreateSpec(
        create_kwargs=kwargs,
        networks=networks,
        primary_network=primary,
    )


def _merge_env(
    container_env: list[str] | None,
    secrets: dict[str, str],
    *,
    previously_injected: set[str],
    image_env: Sequence[str] = (),
) -> dict[str, str]:
    """Overlay fresh secrets on the container's own environment.

    Three rules, in order:

    1. Keys SSM injected last time (``<prefix>.keys``) but which the config
       no longer carries are PRUNED. Without this a merge would leak a
       deleted secret into the workload forever -- the label is the only
       thing that distinguishes "SSM put this here" from "the app has always
       had it".
    2. Entries identical to the image's own defaults are dropped, so an
       image upgrade that changes one still reaches the container.
    3. The fresh secrets win over everything.
    """
    env = _parse_env(container_env)
    for stale in previously_injected - set(secrets):
        env.pop(stale, None)
    for key, value in _parse_env(list(image_env)).items():
        if env.get(key) == value and key not in secrets:
            env.pop(key, None)
    env.update(secrets)
    return env


def _parse_env(entries: list[str] | None) -> dict[str, str]:
    """Parse ``["K=v", ...]`` inspect entries; split on the FIRST ``=``."""
    env: dict[str, str] = {}
    for entry in entries or []:
        key, _sep, value = entry.partition("=")
        if key:
            env[key] = value
    return env


def _split_keys(raw: str | None) -> set[str]:
    return {key.strip() for key in (raw or "").split(",") if key.strip()}


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
    labels: dict[str, str] | None,
    revision: str | None,
    secrets: dict[str, str],
) -> dict[str, str]:
    """Clone the labels, stamping the held revision and the injected keys.

    ``revision=None`` means "this container is not an SSM unit" (a netns
    passenger being re-pointed): its labels are cloned untouched, so SSM
    never acquires ownership of a container it merely had to move.
    """
    merged = dict(labels or {})
    if revision is None:
        return merged
    merged[REVISION_LABEL] = revision
    # The key names are what the NEXT recreate diffs against to prune a key
    # that has since been deleted from the config.
    merged[KEYS_LABEL] = ",".join(sorted(secrets))
    return merged


def _external_owner(labels: dict[str, str]) -> str | None:
    """The other tool that created this container, if any."""
    for label in EXTERNAL_OWNER_LABELS:
        owner = labels.get(label)
        if owner:
            return owner
    return None


def _name_of(container: Any, attrs: dict[str, Any]) -> str:
    name = getattr(container, "name", None)
    if isinstance(name, str) and name:
        return name
    return str(attrs.get("Name") or "").lstrip("/")


def _age_seconds(created: Any, now: datetime) -> float | None:
    """Seconds since the container was created; None when unparseable.

    None means "unknown", and every caller treats an unknown lifecycle fact
    as permissive -- the settling window is a guard against yanking a
    container mid-deploy, not a reason to stop reloading a fleet whose
    timestamps we cannot read.
    """
    if not isinstance(created, str) or not created:
        return None
    try:
        stamp = datetime.fromisoformat(
            _NANOS.sub(r"\1", created).replace("Z", "+00:00")
        )
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return max((now - stamp).total_seconds(), 0.0)


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

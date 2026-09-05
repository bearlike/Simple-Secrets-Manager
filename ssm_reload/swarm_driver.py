"""Docker Swarm implementation of the :class:`ReloadDriver` seam.

Swarm is a genuinely different runtime shape from a plain Docker host, not
just a bigger one, and that shape drives every decision below:

* A container's env is frozen at *create* time on a single host; a Swarm
  **service**'s desired state lives on the manager and is rolled out to
  whichever node a task lands on. So there is no "recreate this container"
  operation here -- the unit of change is the *service*, and the mechanism is
  ``docker service update``, which Swarm itself turns into a rolling
  replacement of that service's tasks, across every node running one.
* Docker secrets/configs are immutable objects, encrypted at rest (secrets)
  or plain (configs), and delivered to a task as a FILE at container-create
  time -- there is no Swarm-native way to inject them as literal environment
  variables the way a plain container's ``Env`` can be merged. Consumers must
  read the mounted file themselves (source it in an entrypoint, or use an
  image that supports ``*_FILE``/``*_SECRETFILE`` env-file conventions). This
  is the deliberate trade for running across multiple nodes: SSM never ships
  secret bytes anywhere Swarm itself would not already replicate them.
* Only a swarm MANAGER can create secrets/configs or update a service, so
  this driver -- unlike :class:`~ssm_reload.docker_driver.DockerDriver`,
  which is meant to run one instance per host -- must run as a SINGLE
  instance with its Docker socket pointed at (or bind-mounted on) a manager
  node. Two instances would race each other minting differently-named
  objects for the same revision.
* Because each rotation mints a brand-new object (Swarm objects cannot be
  edited in place), old objects accumulate unless something prunes them.
  :meth:`SwarmDriver.gc` deletes any object under our namespace that no
  running service still references -- computed fresh from live cluster
  state each pass, so it holds no durable state of its own, consistent with
  the rest of ssm-reload.
* A Swarm secret's mount point is FIXED at ``/run/secrets/<name>`` -- only
  the filename is customizable, not the directory. A config has no such
  restriction, so its mount directory is a setting
  (``SSM_RELOAD_SWARM_CONFIG_MOUNT_DIR``, default ``/run/ssm``) rather than
  hardcoded. ``apply`` picks the target accordingly per
  :attr:`SwarmDriver.secret_kind`.
* ``docker service ls``'s own ``label`` filter only ever matches a
  service's OWN labels (``Spec.Labels``, i.e. Compose's ``deploy.labels``),
  never its task template's container labels (Compose's plain ``labels:``
  under a service). Relying on that filter at discovery time would silently
  drop a service opted in the "wrong" way -- an easy mix-up, since a plain
  container reads the opposite ("container-level") labels. ``discover``
  therefore fetches every service and checks BOTH label sources itself.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from ssm_projection import env_filename, render_dotenv
from ssm_reload.config import (
    CONFIG_LABEL,
    ENABLE_LABEL,
    OWNER_LABEL,
    REVISION_LABEL,
    SWARM_OBJECT_PREFIX,
    SwarmSecretKind,
)
from ssm_reload.docker_driver import _age_seconds, _docker
from ssm_reload.errors import BindingError, DriverError
from ssm_reload.models import Binding, ConfigRef, Lifecycle, Unit

logger = logging.getLogger("ssm_reload.swarm_driver")


def _object_name(ref: ConfigRef, revision: str) -> str:
    """The Swarm object name for one revision of one config.

    Includes a content hash of the revision (rather than the raw ETag,
    which may hold characters Swarm object names reject) so every rotation
    gets its own immutable object, and the same revision always maps back
    to the same name -- a retried apply reuses the object instead of
    minting a duplicate.
    """
    digest = hashlib.sha256(revision.encode("utf-8")).hexdigest()[:12]
    return f"{SWARM_OBJECT_PREFIX}-{ref.project}-{ref.config}-{digest}"


def _object_prefix(ref: ConfigRef) -> str:
    """Every object name ssm-reload has ever minted for this config."""
    return f"{SWARM_OBJECT_PREFIX}-{ref.project}-{ref.config}-"


def _target(
    secret_kind: SwarmSecretKind, config_mount_dir: str, filename: str
) -> str:
    """Where ``filename`` is mounted for this object kind.

    A secret's directory is fixed by Swarm itself (``/run/secrets/``); a
    config has no such restriction, so it is placed under
    ``config_mount_dir`` (``SSM_RELOAD_SWARM_CONFIG_MOUNT_DIR``) instead.
    """
    if secret_kind == "secret":
        return filename
    return f"{config_mount_dir}/{filename}"


class SwarmDriver:
    """Manage Swarm services opted in via ``<prefix>.enable=true``.

    ``secret_kind`` picks the Swarm object type used to deliver a config's
    content: ``"secret"`` (encrypted at rest -- the default) or ``"config"``
    (plain). Either way the payload is the SAME dotenv document the
    non-swarm driver projects to a file, so an image that already knows how
    to read one can be pointed at the mounted path unchanged.
    """

    # A service is never itself "started"; its tasks are. Watch create/update
    # on the service object so a redeploy is adopted near-instantly.
    EVENT_TYPE = "service"
    EVENT_ACTIONS = ["create", "update"]

    def __init__(
        self,
        *,
        secret_kind: SwarmSecretKind = "secret",
        config_mount_dir: str = "/run/ssm",
        client: Any = None,
    ) -> None:
        self.secret_kind = secret_kind
        self.config_mount_dir = config_mount_dir
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = _docker().from_env()
        return self._client

    @property
    def _objects(self) -> Any:
        if self.secret_kind == "secret":
            return self.client.secrets
        return self.client.configs

    def discover(self) -> list[Unit]:
        # Fetch every service rather than filtering server-side: Docker's
        # own `label` filter on this endpoint only ever inspects a
        # service's OWN labels, never its task template's container labels
        # -- see the module docstring. `_is_enabled` checks both.
        try:
            services = self.client.services.list()
        except Exception as exc:
            raise DriverError(
                "Could not list Swarm services -- is this node's Docker "
                f"socket a swarm MANAGER? {exc}"
            ) from exc
        now = datetime.now(timezone.utc)
        return [
            Unit(
                id=service.id,
                name=service.name,
                raw=service,
                lifecycle=self._lifecycle(service, now),
            )
            for service in services
            if _is_enabled(service)
        ]

    def _lifecycle(self, service: Any, now: datetime) -> Lifecycle:
        # Services have no per-task "created but not started" state to read
        # cheaply, and no netns-sharing concept between them -- overlay
        # networks make that unnecessary. The settling window still guards
        # against racing an operator's OWN `docker service update` /
        # `docker stack deploy` that just landed on this same service.
        attrs = service.attrs or {}
        return Lifecycle(
            owner=None,
            status="running",
            age_seconds=_age_seconds(attrs.get("UpdatedAt"), now),
            dependents=(),
        )

    def read_binding(self, unit: Unit) -> Binding:
        labels = _labels(unit.raw)
        config_label = labels.get(CONFIG_LABEL)
        if not config_label:
            raise BindingError(f"{unit.name}: missing '{CONFIG_LABEL}' label")
        try:
            ref = ConfigRef.parse(config_label)
        except BindingError as exc:
            raise BindingError(f"{unit.name}: {CONFIG_LABEL} {exc}") from exc
        return Binding(
            project=ref.project,
            config=ref.config,
            held_revision=labels.get(REVISION_LABEL) or None,
        )

    def read_env(self, unit: Unit) -> dict[str, str]:
        # Secrets are delivered as a mounted FILE, never as literal service
        # env -- there is nothing here to compare against `secrets`, so this
        # always reports empty. `held_revision == new_etag` (checked before
        # this is ever consulted) is what makes the steady state cheap; a
        # non-empty `secrets` map can never look "already current" via env,
        # which is the safe direction to be wrong in.
        return {}

    def read_managed_keys(self, unit: Unit) -> set[str]:
        # The delivered object IS the full rendered document each rotation,
        # so a key removed from a config is simply absent from the next
        # object -- there is no leftover-env-var hazard to track here.
        return set()

    def apply(self, unit: Unit, env: dict[str, str], revision: str) -> None:
        """Roll ``unit``'s service onto a freshly minted secret/config object.

        Creates (or reuses, if a previous attempt got this far and failed
        later) an immutable object named after ``revision``, then updates the
        service to reference it in place of any earlier object under this
        config's namespace -- which is what makes Swarm itself roll the
        change out to every task, on every node, via its own rolling-update
        policy.
        """
        service = unit.raw
        binding = self.read_binding(unit)
        ref = ConfigRef(binding.project, binding.config)
        filename = env_filename(ref.project, ref.config)
        target = _target(self.secret_kind, self.config_mount_dir, filename)
        content = render_dotenv(env).encode("utf-8")

        try:
            object_id, object_name = self._ensure_object(
                ref, revision, content
            )
            self._update_service(
                service, object_id, object_name, target, revision
            )
        except DriverError:
            raise
        except Exception as exc:
            raise DriverError(
                f"{unit.name}: swarm rollout failed: {exc}"
            ) from exc

    def _ensure_object(
        self, ref: ConfigRef, revision: str, content: bytes
    ) -> tuple[str, str]:
        name = _object_name(ref, revision)
        docker = _docker()
        try:
            created = self._objects.create(
                name=name,
                data=content,
                labels={
                    OWNER_LABEL: "ssm-reload",
                    CONFIG_LABEL: str(ref),
                },
            )
            return created.id, name
        except docker.errors.APIError as exc:
            if exc.response is not None and exc.response.status_code == 409:
                # Same revision, retried after a failure past this point:
                # reuse the object instead of erroring on "already exists".
                existing = self._objects.get(name)
                return existing.id, name
            raise DriverError(
                f"could not create {self.secret_kind} {name}: {exc}"
            ) from exc

    def _update_service(
        self,
        service: Any,
        object_id: str,
        object_name: str,
        target: str,
        revision: str,
    ) -> None:
        docker = _docker()
        kind_kwarg = "secrets" if self.secret_kind == "secret" else "configs"
        reference_cls = (
            docker.types.SecretReference
            if self.secret_kind == "secret"
            else docker.types.ConfigReference
        )
        # Match on the MOUNT TARGET, not our own naming prefix: a service
        # can carry at most one reference per target path anyway (Swarm
        # rejects two), and this is what lets a manually pre-created
        # bootstrap secret/config at the same target be taken over cleanly
        # instead of erroring as a duplicate mount.
        existing = _current_references(service, self.secret_kind)
        kept = [
            r for r in existing if (r.get("File") or {}).get("Name") != target
        ]
        new_reference = reference_cls(
            object_id, object_name, filename=target, mode=0o440
        )
        labels = dict(_labels(service))
        labels[REVISION_LABEL] = revision
        try:
            service.update(
                fetch_current_spec=True,
                labels=labels,
                **{kind_kwarg: [*_reference_objects(kept), new_reference]},
            )
        except Exception as exc:
            raise DriverError(
                f"{service.name}: service update failed: {exc}"
            ) from exc

    def gc(self) -> None:
        """Delete rotated objects no service currently references.

        Recomputed from live cluster state every call -- never persisted --
        because an object cannot safely be deleted the moment a new one is
        minted: Swarm refuses to delete a secret/config still bound to a
        task that has not rolled over yet. Waiting until no service
        references it at all is what makes this safe to run every pass.
        """
        try:
            services = self.client.services.list()
        except Exception as exc:
            logger.warning("gc: could not list services: %s", exc)
            return
        referenced: set[str] = set()
        for service in services:
            for kind in ("secret", "config"):
                for reference in _current_references(service, kind):
                    ref_id = reference.get("SecretID") or reference.get(
                        "ConfigID"
                    )
                    if ref_id:
                        referenced.add(ref_id)

        try:
            objects = self._objects.list(
                filters={"label": f"{OWNER_LABEL}=ssm-reload"}
            )
        except Exception as exc:
            logger.warning(
                "gc: could not list %s objects: %s", self.secret_kind, exc
            )
            return
        for obj in objects:
            if obj.id in referenced:
                continue
            try:
                obj.remove()
                logger.info(
                    "gc: removed unreferenced %s %s",
                    self.secret_kind,
                    obj.name,
                )
            except Exception as exc:
                logger.warning(
                    "gc: could not remove %s %s: %s",
                    self.secret_kind,
                    getattr(obj, "name", obj.id),
                    exc,
                )


def _service_labels(service: Any) -> dict[str, str]:
    return ((service.attrs or {}).get("Spec") or {}).get("Labels") or {}


def _container_labels(service: Any) -> dict[str, str]:
    spec = ((service.attrs or {}).get("Spec") or {}).get("TaskTemplate") or {}
    return (spec.get("ContainerSpec") or {}).get("Labels") or {}


def _labels(service: Any) -> dict[str, str]:
    """Service labels (``deploy.labels``) merged over container/task labels
    (plain ``labels:``) -- either placement works, and service labels win
    on a conflict since that is where ssm-reload writes its own.
    """
    return {**_container_labels(service), **_service_labels(service)}


def _is_enabled(service: Any) -> bool:
    return _labels(service).get(ENABLE_LABEL) == "true"


def _current_references(service: Any, kind: str) -> list[dict[str, Any]]:
    spec = ((service.attrs or {}).get("Spec") or {}).get("TaskTemplate") or {}
    container_spec = spec.get("ContainerSpec") or {}
    key = "Secrets" if kind == "secret" else "Configs"
    return list(container_spec.get(key) or [])


def _reference_objects(raw_refs: list[dict[str, Any]]) -> list[Any]:
    """Rebuild SDK reference objects from the raw spec dicts we kept.

    ``service.update`` expects ``SecretReference``/``ConfigReference``
    instances, not the plain dicts ``docker inspect`` returns -- so a
    reference we are NOT touching must still be round-tripped through the
    SDK's own type rather than passed through as-is.
    """
    docker = _docker()
    rebuilt = []
    for raw in raw_refs:
        file_ = raw.get("File") or {}
        is_secret = "SecretID" in raw
        cls = (
            docker.types.SecretReference
            if is_secret
            else docker.types.ConfigReference
        )
        rebuilt.append(
            cls(
                raw.get("SecretID") or raw.get("ConfigID"),
                raw.get("SecretName") or raw.get("ConfigName"),
                filename=file_.get("Name"),
                uid=file_.get("UID", "0"),
                gid=file_.get("GID", "0"),
                mode=file_.get("Mode", 0o444),
            )
        )
    return rebuilt

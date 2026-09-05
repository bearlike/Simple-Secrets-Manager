"""Service runner: wires config, client, and driver to the loop.

``reconcile`` is fired on two triggers:

* a periodic poll every ``SSM_RELOAD_POLL_INTERVAL`` seconds, and
* the Docker event stream (container ``start``/``create``, or in swarm mode
  service ``create``/``update``, carrying the fixed
  ``com.bearlike.ssm.enable=true`` label) for near-instant adoption of new or
  redeployed units.

Both triggers call the same idempotent :func:`reconcile`; the event
stream just wakes it up sooner. The runner keeps no DURABLE state -- its
one in-process :class:`~ssm_reload.reconcile.AdoptionCache` is rebuilt
from observation after a restart (one extra unconditional export per
adopted unit).
"""

from __future__ import annotations

import logging
import signal
import socket
import threading
from types import FrameType
from typing import TYPE_CHECKING, Any, Mapping

import ssm_telemetry
from ssm_contracts import Trigger
from ssm_projection import DirectorySink, ProjectionSink
from ssm_reload import __version__
from ssm_reload.client import SsmClient
from ssm_reload.config import (
    ENABLE_LABEL,
    PROJECTION_DIR,
    PROJECTION_VOLUME,
    ReloadSettings,
)
from ssm_reload.docker_driver import DockerDriver, require_docker_sdk
from ssm_reload.errors import SsmReloadError
from ssm_reload.projection import Projector
from ssm_reload.reconcile import Reconciler
from ssm_reload.swarm_driver import SwarmDriver

if TYPE_CHECKING:
    from ssm_reload.driver import ReloadDriver

logger = logging.getLogger("ssm_reload.runner")


class Runner:
    """Owns the wake-up event, poll thread, and event-stream thread."""

    def __init__(
        self,
        settings: ReloadSettings,
        driver: "ReloadDriver",
        reconciler: Reconciler,
        *,
        host: str | None = None,
    ) -> None:
        self.settings = settings
        self.driver = driver
        # The reconciler holds the pass-to-pass memory (adoptions, projected
        # revisions), so it is built once and reused -- not re-wired per pass.
        self.reconciler = reconciler
        self.host = host or socket.gethostname()
        self._stop = threading.Event()
        # Both the poll thread and the event thread fire run_once; a
        # recreate's own create/start events can wake the event thread
        # mid-recreate. Serialize so passes never overlap (which would
        # risk backup-name collisions during a non-destructive recreate),
        # and so the reconciler's memory has a single writer.
        self._reconcile_lock = threading.Lock()

    def run_once(self, trigger: Trigger = "poll") -> None:
        """Run a single reconcile pass, swallowing unexpected errors.

        ``trigger`` records what woke this pass ("startup"/"poll"/"event") so
        every status report carries it into the fleet view.
        """
        with self._reconcile_lock:
            try:
                self.reconciler.run(trigger)
                # Swarm mode only: prune rotated secret/config objects no
                # service references any more. Recomputed from live cluster
                # state, so it is safe to run every pass -- see
                # SwarmDriver.gc.
                gc = getattr(self.driver, "gc", None)
                if gc is not None:
                    gc()
            except SsmReloadError as exc:
                logger.warning("Reconcile pass skipped: %s", exc)
            except Exception as exc:  # keep the daemon alive on failure.
                logger.exception("Unexpected reconcile error: %s", exc)

    def _poll_loop(self) -> None:
        # The first pass at process start is "startup"; every later tick is a
        # plain "poll".
        trigger: Trigger = "startup"
        while not self._stop.is_set():
            self.run_once(trigger)
            trigger = "poll"
            self._stop.wait(self.settings.poll_interval)

    def _event_loop(self) -> None:
        label = f"{ENABLE_LABEL}=true"
        # DockerDriver watches container start/create; SwarmDriver watches
        # service create/update (a service is never "started" itself -- its
        # tasks are). Read off the driver rather than branching on its type,
        # so a future driver just declares its own pair.
        event_type = getattr(self.driver, "EVENT_TYPE", "container")
        event_actions = getattr(
            self.driver, "EVENT_ACTIONS", ["start", "create"]
        )
        while not self._stop.is_set():
            try:
                # `.client` (the underlying docker-py client) is a shared
                # implementation detail of both Docker-based drivers, not
                # part of the driver-agnostic `ReloadDriver` seam -- read via
                # getattr so a future non-Docker driver isn't forced to grow
                # a mismatched attribute just to satisfy this loop.
                docker_client = getattr(self.driver, "client")
                events = docker_client.events(
                    decode=True,
                    filters={
                        "type": event_type,
                        "event": event_actions,
                        "label": label,
                    },
                )
                for _event in events:
                    if self._stop.is_set():
                        break
                    self.run_once("event")
            except Exception as exc:  # reconnect after transient failures.
                if self._stop.is_set():
                    break
                logger.warning("Event stream error: %s; retrying", exc)
                self._stop.wait(self.settings.poll_interval)

    def start(self) -> None:
        """Block running both triggers until interrupted."""
        logger.info(
            "ssm-reload starting: host=%s poll=%ss",
            self.host,
            self.settings.poll_interval,
        )
        # Best-effort, and DockerDriver-only: makes the volume a first-class
        # Docker object that consumer stacks can declare `external: true`,
        # and warns if an existing one would put projected secrets on the
        # host's disk. Swarm mode delivers via secret/config objects instead
        # and has no local volume to create.
        ensure_volume = getattr(self.driver, "ensure_volume", None)
        if ensure_volume is not None:
            ensure_volume(PROJECTION_VOLUME)
            logger.info("Projecting to %s", PROJECTION_DIR)
        event_thread = threading.Thread(
            target=self._event_loop, name="ssm-reload-events", daemon=True
        )
        event_thread.start()
        self._poll_loop()

    def stop(self, *_args: Any) -> None:
        self._stop.set()


def build_runner(settings: ReloadSettings) -> Runner:
    # The composition root: every collaborator is constructed here and
    # injected, so nothing below reaches for its own dependencies.
    # The token is unwrapped only here, at its single point of use.
    client = SsmClient(settings.base_url, settings.token.get_secret_value())
    driver: "ReloadDriver"
    sink: ProjectionSink
    if settings.swarm_mode:
        driver = SwarmDriver(
            secret_kind=settings.swarm_secret_kind,
            config_mount_dir=settings.swarm_config_mount_dir,
        )
        # Delivery IS the Swarm secret/config object in this mode; there is
        # no local file for anything to read, so projecting one would only
        # ever fail (no volume mounted) or mislead (a file nothing reads).
        sink = _NullSink()
    else:
        driver = DockerDriver()
        sink = DirectorySink(PROJECTION_DIR)
    reconciler = Reconciler(
        driver,
        client,
        socket.gethostname(),
        Projector(sink),
        bootstrap_configs=settings.bootstrap_configs,
    )
    return Runner(settings, driver, reconciler, host=reconciler.host)


class _NullSink:
    """No-op :class:`ProjectionSink` for swarm mode.

    ``exists`` reports true unconditionally, so :class:`Projector` never
    forces an unconditional export chasing a "missing" file that was never
    meant to be written; ``write`` does nothing and says so.
    """

    def write(
        self, project: str, config: str, secrets: Mapping[str, str]
    ) -> str:
        return "swarm secret/config object (no local file projected)"

    def exists(self, project: str, config: str) -> bool:
        return True


def main() -> int:
    # Build (and validate) settings first: a bad env var fails fast with a
    # clean SsmReloadError instead of a raw pydantic traceback. Logging is
    # configured from the validated level right after.
    try:
        settings = ReloadSettings.load()
    except SsmReloadError as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Wire OTel event emission once. No-op unless an OTLP endpoint is
    # configured (and the `otel` extra is installed), so this costs nothing by
    # default; the endpoint is injected from settings, never read from env.
    ssm_telemetry.configure(
        "ssm-reload", __version__, endpoint=settings.otel_endpoint
    )

    try:
        # Fail fast + clean if the reload extra (Docker SDK) is absent,
        # rather than spinning in the loop logging skip warnings.
        require_docker_sdk()
    except SsmReloadError as exc:
        logger.error("%s", exc)
        return 2

    runner = build_runner(settings)

    def _handle(_signum: int, _frame: FrameType | None) -> None:
        logger.info("Shutting down")
        runner.stop()

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    runner.start()
    return 0

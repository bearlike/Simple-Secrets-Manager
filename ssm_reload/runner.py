"""Service runner: wires config, client, and driver to the loop.

``reconcile`` is fired on two triggers:

* a periodic poll every ``SSM_RELOAD_POLL_INTERVAL`` seconds, and
* the Docker event stream (container ``start``/``create`` carrying the
  fixed ``com.bearlike.ssm.enable=true`` label) for near-instant adoption
  of new or redeployed containers.

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
from typing import Any

import ssm_telemetry
from ssm_contracts import Trigger
from ssm_projection import DirectorySink
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

logger = logging.getLogger("ssm_reload.runner")


class Runner:
    """Owns the wake-up event, poll thread, and event-stream thread."""

    def __init__(
        self,
        settings: ReloadSettings,
        driver: DockerDriver,
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
        while not self._stop.is_set():
            try:
                events = self.driver.client.events(
                    decode=True,
                    filters={
                        "type": "container",
                        "event": ["start", "create"],
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
            "ssm-reload starting: host=%s poll=%ss projecting to %s",
            self.host,
            self.settings.poll_interval,
            PROJECTION_DIR,
        )
        # Best-effort: makes the volume a first-class Docker object that
        # consumer stacks can declare `external: true`, and warns if an
        # existing one would put projected secrets on the host's disk.
        self.driver.ensure_volume(PROJECTION_VOLUME)
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
    driver = DockerDriver()
    reconciler = Reconciler(
        driver,
        client,
        socket.gethostname(),
        Projector(DirectorySink(PROJECTION_DIR)),
        bootstrap_configs=settings.bootstrap_configs,
    )
    return Runner(settings, driver, reconciler, host=reconciler.host)


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

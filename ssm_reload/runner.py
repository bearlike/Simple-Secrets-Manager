"""Service runner: wires config, client, and driver to the loop.

``reconcile`` is fired on two triggers:

* a periodic poll every ``SSM_RELOAD_POLL_INTERVAL`` seconds, and
* the Docker event stream (container ``start``/``create`` carrying the
  ``ssm.enable=true`` label) for near-instant adoption of new or
  redeployed containers.

Both triggers call the same idempotent :func:`reconcile`; the event
stream just wakes it up sooner. The runner keeps no state.
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
from types import FrameType
from typing import Any

from ssm_reload.client import SsmClient
from ssm_reload.config import Config
from ssm_reload.docker_driver import DockerDriver, require_docker_sdk
from ssm_reload.errors import SsmReloadError
from ssm_reload.reconcile import reconcile

logger = logging.getLogger("ssm_reload.runner")


class Runner:
    """Owns the wake-up event, poll thread, and event-stream thread."""

    def __init__(
        self,
        config: Config,
        client: SsmClient,
        driver: DockerDriver,
        *,
        host: str | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.driver = driver
        self.host = host or socket.gethostname()
        self._stop = threading.Event()
        # Both the poll thread and the event thread fire run_once; a
        # recreate's own create/start events can wake the event thread
        # mid-recreate. Serialize so passes never overlap (which would
        # risk backup-name collisions during a non-destructive recreate).
        self._reconcile_lock = threading.Lock()

    def run_once(self) -> None:
        """Run a single reconcile pass, swallowing unexpected errors."""
        with self._reconcile_lock:
            try:
                reconcile(self.driver, self.client, self.host)
            except SsmReloadError as exc:
                logger.warning("Reconcile pass skipped: %s", exc)
            except Exception as exc:  # keep the daemon alive on failure.
                logger.exception("Unexpected reconcile error: %s", exc)

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            self.run_once()
            self._stop.wait(self.config.poll_interval)

    def _event_loop(self) -> None:
        label = f"{self.config.label_prefix}.enable=true"
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
                    self.run_once()
            except Exception as exc:  # reconnect after transient failures.
                if self._stop.is_set():
                    break
                logger.warning("Event stream error: %s; retrying", exc)
                self._stop.wait(self.config.poll_interval)

    def start(self) -> None:
        """Block running both triggers until interrupted."""
        logger.info(
            "ssm-reload starting: host=%s poll=%ss prefix=%s",
            self.host,
            self.config.poll_interval,
            self.config.label_prefix,
        )
        event_thread = threading.Thread(
            target=self._event_loop, name="ssm-reload-events", daemon=True
        )
        event_thread.start()
        self._poll_loop()

    def stop(self, *_args: Any) -> None:
        self._stop.set()


def build_runner(config: Config) -> Runner:
    client = SsmClient(config.base_url, config.token)
    driver = DockerDriver(
        label_prefix=config.label_prefix,
        docker_host=config.docker_host,
    )
    return Runner(config, client, driver)


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("SSM_RELOAD_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        config = Config.from_env()
    except SsmReloadError as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    try:
        # Fail fast + clean if the reload extra (Docker SDK) is absent,
        # rather than spinning in the loop logging skip warnings.
        require_docker_sdk()
    except SsmReloadError as exc:
        logger.error("%s", exc)
        return 2

    runner = build_runner(config)

    def _handle(_signum: int, _frame: FrameType | None) -> None:
        logger.info("Shutting down")
        runner.stop()

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    runner.start()
    return 0

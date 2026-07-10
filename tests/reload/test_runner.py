"""Runner-level tests: reconcile must run serially.

The poll thread and the Docker event thread both fire ``run_once``; a
recreate's own create/start events can wake the event thread mid-recreate.
A single lock guards the reconcile entry so passes never overlap (which,
with the non-destructive recreate, would risk backup-name collisions) and so
the reconciler's pass-to-pass memory has exactly one writer.

The reconciler is INJECTED, so these tests substitute a spy rather than
monkeypatching a module symbol (which would silently no-op the day that
symbol moves).
"""

from __future__ import annotations

import threading
import time
from typing import cast

from pydantic import SecretStr

from ssm_contracts import Trigger
from ssm_reload.config import ReloadSettings
from ssm_reload.docker_driver import DockerDriver
from ssm_reload.reconcile import Reconciler
from ssm_reload.runner import Runner


class SpyReconciler:
    """Records whether two passes were ever in flight at the same time."""

    def __init__(self) -> None:
        self.active = 0
        self.overlaps: list[bool] = []
        self.triggers: list[Trigger] = []
        self._guard = threading.Lock()

    def run(self, trigger: Trigger = "poll") -> None:
        with self._guard:
            self.active += 1
            self.triggers.append(trigger)
            if self.active > 1:
                self.overlaps.append(True)
        time.sleep(0.02)  # widen the window an overlap would show up in.
        with self._guard:
            self.active -= 1


class ExplodingReconciler:
    def run(self, trigger: Trigger = "poll") -> None:
        raise RuntimeError("docker socket vanished")


def _runner(reconciler: object) -> Runner:
    settings = ReloadSettings(base_url="http://ssm", token=SecretStr("t"))
    return Runner(
        settings,
        cast(DockerDriver, object()),
        cast(Reconciler, reconciler),
        host="h",
    )


def test_run_once_serializes_reconcile() -> None:
    reconciler = SpyReconciler()
    runner = _runner(reconciler)

    threads = [threading.Thread(target=runner.run_once) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert reconciler.overlaps == []
    assert len(reconciler.triggers) == 6


def test_run_once_keeps_the_daemon_alive_when_a_pass_explodes(caplog) -> None:
    # The poll loop must survive anything a pass throws, or one bad container
    # takes the whole fleet's reloader down until someone restarts it.
    runner = _runner(ExplodingReconciler())

    with caplog.at_level("ERROR"):
        runner.run_once()

    assert "docker socket vanished" in caplog.text

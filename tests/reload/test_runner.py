"""Runner-level tests: reconcile must run serially.

The poll thread and the Docker event thread both fire ``run_once``; a
recreate's own create/start events can wake the event thread mid-recreate.
A single lock guards the reconcile entry so passes never overlap (which,
with the non-destructive recreate, would risk backup-name collisions).
"""

from __future__ import annotations

import threading
import time

import ssm_reload.runner as runner_mod
from ssm_reload.config import Config
from ssm_reload.runner import Runner


def test_run_once_serializes_reconcile(monkeypatch):
    active = {"n": 0}
    overlaps: list[bool] = []
    guard = threading.Lock()

    def fake_reconcile(_driver, _client, _host):
        with guard:
            active["n"] += 1
            if active["n"] > 1:
                overlaps.append(True)
        time.sleep(0.02)  # widen the window an overlap would show up in.
        with guard:
            active["n"] -= 1

    monkeypatch.setattr(runner_mod, "reconcile", fake_reconcile)

    config = Config(base_url="http://ssm", token="t")
    runner = Runner(config, client=object(), driver=object(), host="h")

    threads = [threading.Thread(target=runner.run_once) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert overlaps == []

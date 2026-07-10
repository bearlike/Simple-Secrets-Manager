"""Reset telemetry global state between tests.

`configure()` wires a process-global provider; without a teardown a test that
activates telemetry would leak its exporter into unrelated tests (emit_event
reads the same global). Shut it back down to the no-op state after each test.
"""

from __future__ import annotations

import pytest

import ssm_telemetry


@pytest.fixture(autouse=True)
def _reset_telemetry():
    yield
    ssm_telemetry.shutdown()

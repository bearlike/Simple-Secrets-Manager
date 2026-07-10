"""Tests for the ssm_telemetry OTel event wrapper.

The load-bearing contract is the zero-cost default: with no endpoint passed to
configure(), emit_event is a no-op and the SDK/exporter are never imported. A
second test asserts events (with event_name + attributes) flow through when an
exporter is injected.
"""

from __future__ import annotations

import subprocess
import sys

import ssm_telemetry


def test_noop_by_default_never_imports_the_sdk():
    # Run in a clean interpreter so the assertion isn't polluted by another
    # test importing the SDK earlier in the session. No endpoint is passed, so
    # configure() must stay a no-op regardless of the ambient environment.
    code = (
        "import sys\n"
        "import ssm_telemetry\n"
        "ssm_telemetry.configure('svc', '1.0')\n"
        "ssm_telemetry.emit_event('e', attributes={'k': 'v'})\n"
        "assert not ssm_telemetry.is_active()\n"
        "assert 'opentelemetry.sdk' not in sys.modules, 'sdk was imported'\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_emit_event_without_configure_is_a_noop():
    # Never configured in this process -> silently does nothing, never raises.
    ssm_telemetry.emit_event("some.event", attributes={"a": "b"})
    assert ssm_telemetry.is_active() is False


def test_instance_id_is_stable_within_a_process():
    assert ssm_telemetry.instance_id() == ssm_telemetry.instance_id()


def test_configured_event_flows_through_with_name_and_attributes():
    from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter

    exporter = InMemoryLogRecordExporter()
    ssm_telemetry.configure("svc", "1.0", exporter=exporter)
    assert ssm_telemetry.is_active() is True

    ssm_telemetry.emit_event(
        "ssm_reload.cycle.completed",
        body="done",
        attributes={"ssm.trigger": "poll", "ssm.project": "web"},
    )

    records = exporter.get_finished_logs()
    assert len(records) == 1
    log_record = records[0].log_record
    assert log_record.event_name == "ssm_reload.cycle.completed"
    assert log_record.attributes["ssm.trigger"] == "poll"
    assert log_record.attributes["ssm.project"] == "web"

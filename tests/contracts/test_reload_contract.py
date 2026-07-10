"""Contract tests for the shared, typed reload models.

These pin the wire format both the reloader and the server rely on: camelCase
aliases, tolerant validation (unknown fields ignored so version drift never
hard-fails), and the enum/slug guards.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ssm_contracts import (
    ReloadReport,
    Reporter,
    UnitStatus,
    is_valid_slug,
    summarize_validation_error,
)


def _report(**overrides):
    base = {
        "project": "web",
        "config": "prod",
        "reporter": Reporter(host="h1", instance_id="i-1", version="0.1.0"),
        "trigger": "poll",
        "revision": '"v2"',
        "outcome": "current",
        "units": [
            UnitStatus(
                id="c1", name="c1", held_revision='"v2"', outcome="current"
            )
        ],
    }
    base.update(overrides)
    return ReloadReport(**base)


def test_dump_by_alias_is_camelcase():
    wire = _report().model_dump(by_alias=True)
    assert wire["reporter"]["instanceId"] == "i-1"
    assert wire["units"][0]["heldRevision"] == '"v2"'


def test_validate_accepts_camelcase_wire_input():
    wire = {
        "project": "web",
        "config": "prod",
        "reporter": {"host": "h1", "instanceId": "i-1", "version": "0.1.0"},
        "trigger": "event",
        "revision": '"v2"',
        "outcome": "updated",
        "units": [
            {
                "id": "c1",
                "name": "c1",
                "heldRevision": '"v1"',
                "outcome": "recreated",
            }
        ],
    }
    report = ReloadReport.model_validate(wire)
    assert report.reporter.instance_id == "i-1"
    assert report.units[0].held_revision == '"v1"'


def test_unknown_fields_are_ignored_for_forward_compat():
    wire = {
        "project": "web",
        "config": "prod",
        "trigger": "poll",
        "outcome": "current",
        "futureField": "from a newer reloader",
        "reporter": {"host": "h1", "somethingNew": 1},
    }
    report = ReloadReport.model_validate(wire)
    assert report.project == "web"
    assert not hasattr(report, "future_field")


def test_invalid_trigger_is_rejected():
    with pytest.raises(ValidationError):
        _report(trigger="bogus")


def test_invalid_slug_is_rejected():
    with pytest.raises(ValidationError):
        _report(project="Not A Slug")


def test_blank_revision_normalizes_to_none():
    assert _report(revision="   ").revision is None


def test_summarize_validation_error_is_one_readable_line():
    try:
        ReloadReport.model_validate({"project": "web"})
    except ValidationError as exc:
        message = summarize_validation_error(exc)
    assert message.startswith("Invalid reload report:")
    assert "\n" not in message


def test_is_valid_slug_uses_fullmatch_semantics():
    # fullmatch mirrors the server: a trailing newline is NOT a slug.
    assert is_valid_slug("my-app_1")
    assert not is_valid_slug("MyApp")
    assert not is_valid_slug("abc\n")
    assert not is_valid_slug("")

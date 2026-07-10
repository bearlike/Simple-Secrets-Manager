from datetime import datetime, timezone

from ssm_server.api.serialization import to_iso


def test_to_iso_emits_z_suffix_for_aware_datetime():
    # The API contract is a "Z"-suffixed ISO string, never "+00:00".
    aware = datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
    assert to_iso(aware) == "2026-01-01T12:30:00Z"


def test_to_iso_shape_identical_for_naive_and_aware():
    # tz_aware=True flips Mongo read-back from naive to aware UTC. This pins
    # that the serialized wire shape does NOT change: a naive value and the
    # equivalent aware value produce byte-identical ISO strings, so the flip
    # is invisible at the API boundary.
    naive = datetime(2026, 1, 1, 12, 30, 0)
    aware = datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
    assert to_iso(naive) == to_iso(aware) == "2026-01-01T12:30:00Z"

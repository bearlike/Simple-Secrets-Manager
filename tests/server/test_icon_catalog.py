"""Pure-function tests for the derived icon-pack catalog.

``secret_icons`` imports no Mongo, so these exercise the real
``icon_index.json`` grouping directly (no fakes needed).
"""

import ssm_server.engines.secret_icons as secret_icons_module
from ssm_server.engines.secret_icons import (
    is_valid_icon_prefix,
    list_icon_names,
    list_icon_prefixes,
)


def test_list_icon_prefixes_is_non_empty_and_sane():
    prefixes = list_icon_prefixes()
    assert prefixes
    slugs = {p["prefix"] for p in prefixes}
    assert "lucide" in slugs
    for entry in prefixes:
        assert entry["prefix"]
        assert entry["count"] >= 1
        # sample is a full slug within its own pack.
        assert entry["sample"].startswith(f"{entry['prefix']}:")


def test_list_icon_prefixes_sorted_by_count_desc():
    counts = [p["count"] for p in list_icon_prefixes()]
    assert counts == sorted(counts, reverse=True)


def test_list_icon_names_contains_known_icon():
    names = list_icon_names("lucide")
    assert names
    assert "key-round" in names
    # names are the bare name half, never the full slug.
    assert all(":" not in name for name in names)
    assert names == sorted(names)


def test_list_icon_names_unknown_prefix_is_empty():
    assert list_icon_names("no-such-pack") == []


def test_prefix_count_matches_distinct_names():
    lucide = next(p for p in list_icon_prefixes() if p["prefix"] == "lucide")
    assert lucide["count"] == len(list_icon_names("lucide"))


def test_is_valid_icon_prefix():
    assert is_valid_icon_prefix("lucide")
    assert is_valid_icon_prefix("simple-icons")
    assert not is_valid_icon_prefix("")
    assert not is_valid_icon_prefix("Lucide")
    assert not is_valid_icon_prefix("lucide:key")
    assert not is_valid_icon_prefix("../etc")


def test_catalog_is_cached_same_object():
    # Timing-free caching check: the derived view is built once per process.
    assert (
        secret_icons_module._icon_pack_catalog()
        is secret_icons_module._icon_pack_catalog()
    )

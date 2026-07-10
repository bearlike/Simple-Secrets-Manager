"""Hermetic tests for Groups delete-path return arity.

delete_group / delete_group_mapping return the 3-tuple (payload, message,
code) — the same shape their create/update siblings use — so resource call
sites can unpack them uniformly.
"""

from bson import ObjectId


from ssm_server.engines.groups import Groups

from tests.server.fakes import FakeCollection


def _groups_with_group(workspace_id, slug):
    group_doc = {"_id": ObjectId(), "workspace_id": workspace_id, "slug": slug}
    return Groups(
        FakeCollection([group_doc]),
        FakeCollection(),
        FakeCollection(),
    )


def test_delete_group_returns_three_tuple_on_success():
    groups = _groups_with_group("w1", "devs")
    assert groups.delete_group("w1", "devs") == (None, "OK", 200)


def test_delete_group_returns_three_tuple_when_missing():
    groups = Groups(FakeCollection(), FakeCollection(), FakeCollection())
    assert groups.delete_group("w1", "ghost") == (
        None,
        "Group not found",
        404,
    )


def test_delete_group_mapping_returns_three_tuple_on_success():
    mapping_id = ObjectId()
    mapping_doc = {"_id": mapping_id, "workspace_id": "w1"}
    groups = Groups(
        FakeCollection(),
        FakeCollection(),
        FakeCollection([mapping_doc]),
    )
    assert groups.delete_group_mapping("w1", str(mapping_id)) == (
        None,
        "OK",
        200,
    )


def test_delete_group_mapping_returns_three_tuple_when_missing():
    groups = Groups(FakeCollection(), FakeCollection(), FakeCollection())
    assert groups.delete_group_mapping("w1", str(ObjectId())) == (
        None,
        "Group mapping not found",
        404,
    )

from bson import ObjectId

from ssm_server.engines.memberships import Memberships

from tests.server.fakes import FakeCollection


def test_list_project_memberships_normalizes_group_ids_for_str_and_objectid():
    workspace_memberships = FakeCollection()
    project_memberships = FakeCollection()
    engine = Memberships(workspace_memberships, project_memberships)

    group_id = ObjectId()
    engine.list_project_memberships_for_subjects(
        workspace_id="w1",
        username="alice",
        group_ids=[group_id],
    )

    assert project_memberships.last_query is not None
    clauses = project_memberships.last_query["$or"]
    group_clause = next(
        item for item in clauses if item.get("subject_type") == "group"
    )
    values = set(group_clause["subject_id"]["$in"])
    assert group_id in values
    assert str(group_id) in values


def test_remove_project_membership_returns_three_tuple_on_success():
    membership_doc = {
        "workspace_id": "w1",
        "project_id": "p1",
        "subject_type": "user",
        "subject_id": "alice",
    }
    engine = Memberships(FakeCollection(), FakeCollection([membership_doc]))
    result = engine.remove_project_membership("w1", "p1", "user", "alice")
    assert result == (None, "OK", 200)


def test_remove_project_membership_returns_three_tuple_when_missing():
    engine = Memberships(FakeCollection(), FakeCollection())
    result = engine.remove_project_membership("w1", "p1", "user", "ghost")
    assert result == (None, "Membership not found", 404)

from bson import ObjectId

from Engines.memberships import Memberships


class FakeCollection:
    def __init__(self):
        self.last_query = None

    def create_index(self, *_args, **_kwargs):
        return None

    def find(self, query):
        self.last_query = query
        return []


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

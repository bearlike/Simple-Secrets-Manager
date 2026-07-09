"""Hermetic engine tests for projects/configs update & delete + cascades.

Mirrors tests/test_configs_list.py: no MongoDB, just an in-memory fake
collection that understands the handful of query operators the engines use.
"""

from datetime import datetime, timezone

from bson import ObjectId

from Engines.configs import Configs
from Engines.memberships import Memberships
from Engines.projects import Projects
from Engines.secrets_v2 import SecretsV2


class _DeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class _UpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count
        self.modified_count = matched_count


def _matches(doc, query):
    for key, cond in query.items():
        value = doc.get(key)
        if isinstance(cond, dict) and "$in" in cond:
            if value not in cond["$in"]:
                return False
        elif value != cond:
            return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction=1):
        self.docs.sort(key=lambda item: item.get(key), reverse=direction == -1)
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    def __iter__(self):
        return iter(self.docs)


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def create_index(self, *_args, **_kwargs):
        return None

    def find(self, query=None, projection=None):
        _ = projection
        query = query or {}
        return FakeCursor([d for d in self.docs if _matches(d, query)])

    def find_one(self, query, projection=None):
        _ = projection
        for doc in self.docs:
            if _matches(doc, query):
                return doc
        return None

    def update_one(self, query, update, upsert=False):
        _ = upsert
        for doc in self.docs:
            if _matches(doc, query):
                doc.update(update.get("$set", {}))
                return _UpdateResult(1)
        return _UpdateResult(0)

    def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if _matches(doc, query):
                del self.docs[index]
                return _DeleteResult(1)
        return _DeleteResult(0)

    def delete_many(self, query):
        keep = [d for d in self.docs if not _matches(d, query)]
        removed = len(self.docs) - len(keep)
        self.docs = keep
        return _DeleteResult(removed)


def _now():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# Projects
# --------------------------------------------------------------------------


def _projects_with(*slugs):
    return Projects(
        FakeCollection(
            [
                {"_id": ObjectId(), "slug": slug, "name": slug.title()}
                for slug in slugs
            ]
        )
    )


def test_project_update_renames():
    projects = _projects_with("alpha")
    doc, code = projects.update("alpha", "Alpha Renamed")
    assert code == 200
    assert doc["name"] == "Alpha Renamed"
    assert doc["slug"] == "alpha"


def test_project_update_missing_is_404():
    projects = _projects_with("alpha")
    msg, code = projects.update("ghost", "Nope")
    assert code == 404
    assert msg == "Project not found"


def test_project_update_blank_name_is_400():
    projects = _projects_with("alpha")
    msg, code = projects.update("alpha", "   ")
    assert code == 400
    assert msg == "Project name is required"


def test_project_delete_removes_doc():
    projects = _projects_with("alpha", "beta")
    doc, code = projects.delete("alpha")
    assert code == 200
    assert doc["slug"] == "alpha"
    assert projects.get_by_slug("alpha") is None
    assert projects.get_by_slug("beta") is not None


def test_project_delete_missing_is_404():
    projects = _projects_with("alpha")
    msg, code = projects.delete("ghost")
    assert code == 404
    assert msg == "Project not found"


# --------------------------------------------------------------------------
# Configs
# --------------------------------------------------------------------------


def _config_doc(slug, project_id, parent_id=None, name=None):
    return {
        "_id": ObjectId(),
        "project_id": project_id,
        "slug": slug,
        "name": name or slug.title(),
        "parent_config_id": parent_id,
        "created_at": _now(),
    }


def test_config_update_renames():
    project_id = "p1"
    base = _config_doc("base", project_id)
    configs = Configs(FakeCollection([base]))
    doc, code = configs.update(project_id, "base", name="Base Env")
    assert code == 200
    assert doc["name"] == "Base Env"
    assert doc["parent_config_id"] is None


def test_config_update_missing_is_404():
    configs = Configs(FakeCollection([]))
    msg, code = configs.update("p1", "ghost", name="x")
    assert code == 404
    assert msg == "Config not found"


def test_config_update_reparent_valid():
    project_id = "p1"
    base = _config_doc("base", project_id)
    dev = _config_doc("dev", project_id)
    configs = Configs(FakeCollection([base, dev]))
    doc, code = configs.update(
        project_id,
        "dev",
        parent_config_id=base["_id"],
        parent_provided=True,
    )
    assert code == 200
    assert doc["parent_config_id"] == base["_id"]


def test_config_update_clear_parent():
    project_id = "p1"
    base = _config_doc("base", project_id)
    dev = _config_doc("dev", project_id, parent_id=base["_id"])
    configs = Configs(FakeCollection([base, dev]))
    doc, code = configs.update(
        project_id, "dev", parent_config_id=None, parent_provided=True
    )
    assert code == 200
    assert doc["parent_config_id"] is None


def test_config_update_parent_not_provided_is_unchanged():
    project_id = "p1"
    base = _config_doc("base", project_id)
    dev = _config_doc("dev", project_id, parent_id=base["_id"])
    configs = Configs(FakeCollection([base, dev]))
    doc, code = configs.update(project_id, "dev", name="Dev")
    assert code == 200
    assert doc["parent_config_id"] == base["_id"]


def test_config_update_rejects_self_parent():
    project_id = "p1"
    base = _config_doc("base", project_id)
    configs = Configs(FakeCollection([base]))
    msg, code = configs.update(
        project_id,
        "base",
        parent_config_id=base["_id"],
        parent_provided=True,
    )
    assert code == 400
    assert msg == "Config cannot be its own parent"


def test_config_update_rejects_cross_project_parent():
    base_other = _config_doc("base", "p2")
    dev = _config_doc("dev", "p1")
    configs = Configs(FakeCollection([base_other, dev]))
    msg, code = configs.update(
        "p1",
        "dev",
        parent_config_id=base_other["_id"],
        parent_provided=True,
    )
    assert code == 400
    assert msg == "Parent config must belong to the same project"


def test_config_update_rejects_cycle():
    project_id = "p1"
    base = _config_doc("base", project_id)
    mid = _config_doc("mid", project_id, parent_id=base["_id"])
    leaf = _config_doc("leaf", project_id, parent_id=mid["_id"])
    configs = Configs(FakeCollection([base, mid, leaf]))
    # Re-parenting base under leaf would loop base -> leaf -> mid -> base.
    msg, code = configs.update(
        project_id,
        "base",
        parent_config_id=leaf["_id"],
        parent_provided=True,
    )
    assert code == 400
    assert msg == "Circular parent reference"


def test_config_delete_leaf():
    project_id = "p1"
    base = _config_doc("base", project_id)
    configs = Configs(FakeCollection([base]))
    doc, code = configs.delete(project_id, "base")
    assert code == 200
    assert doc["slug"] == "base"
    assert configs.get_by_slug(project_id, "base") is None


def test_config_delete_missing_is_404():
    configs = Configs(FakeCollection([]))
    msg, code = configs.delete("p1", "ghost")
    assert code == 404
    assert msg == "Config not found"


def test_config_delete_with_child_is_409():
    project_id = "p1"
    base = _config_doc("base", project_id)
    child = _config_doc("dev", project_id, parent_id=base["_id"])
    configs = Configs(FakeCollection([base, child]))
    msg, code = configs.delete(project_id, "base")
    assert code == 409
    assert "child configs" in msg
    # Nothing was deleted.
    assert configs.get_by_slug(project_id, "base") is not None


def test_config_delete_all_for_project():
    base = _config_doc("base", "p1")
    dev = _config_doc("dev", "p1")
    other = _config_doc("base", "p2")
    collection = FakeCollection([base, dev, other])
    configs = Configs(collection)
    removed_ids = configs.delete_all_for_project("p1")
    assert set(removed_ids) == {base["_id"], dev["_id"]}
    assert [d["slug"] for d in collection.docs] == ["base"]
    assert collection.docs[0]["project_id"] == "p2"


# --------------------------------------------------------------------------
# Secrets cascade
# --------------------------------------------------------------------------


def test_secrets_delete_by_config():
    c1, c2 = ObjectId(), ObjectId()
    secrets = FakeCollection(
        [
            {"config_id": c1, "key": "A"},
            {"config_id": c1, "key": "B"},
            {"config_id": c2, "key": "C"},
        ]
    )
    engine = SecretsV2(secrets, configs_engine=None)
    assert engine.delete_by_config(c1) == 2
    assert [d["key"] for d in secrets.docs] == ["C"]


def test_secrets_delete_by_configs():
    c1, c2, c3 = ObjectId(), ObjectId(), ObjectId()
    secrets = FakeCollection(
        [
            {"config_id": c1, "key": "A"},
            {"config_id": c2, "key": "B"},
            {"config_id": c3, "key": "C"},
        ]
    )
    engine = SecretsV2(secrets, configs_engine=None)
    assert engine.delete_by_configs([c1, c2]) == 2
    assert [d["key"] for d in secrets.docs] == ["C"]
    assert engine.delete_by_configs([]) == 0


# --------------------------------------------------------------------------
# Membership cascade
# --------------------------------------------------------------------------


def test_membership_remove_all_for_project():
    project_id = ObjectId()
    project_memberships = FakeCollection(
        [
            {
                "workspace_id": "w1",
                "project_id": project_id,
                "subject_type": "user",
                "subject_id": "alice",
            },
            {
                "workspace_id": "w1",
                "project_id": str(project_id),
                "subject_type": "group",
                "subject_id": "g1",
            },
            {
                "workspace_id": "w1",
                "project_id": ObjectId(),
                "subject_type": "user",
                "subject_id": "bob",
            },
        ]
    )
    memberships = Memberships(FakeCollection([]), project_memberships)
    memberships.remove_all_for_project("w1", project_id)
    # Both the ObjectId-keyed and string-keyed rows for the project go away;
    # the unrelated project's membership survives.
    assert len(project_memberships.docs) == 1
    assert project_memberships.docs[0]["subject_id"] == "bob"

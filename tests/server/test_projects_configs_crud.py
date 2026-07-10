"""Hermetic engine tests for projects/configs update & delete + cascades.

Mirrors tests/test_configs_list.py: no MongoDB, just an in-memory fake
collection that understands the handful of query operators the engines use.
"""

from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ssm_server.api.serialization import to_iso
from ssm_server.engines.configs import Configs
from ssm_server.engines.memberships import Memberships
from ssm_server.engines.projects import Projects
from ssm_server.engines.secrets_v2 import SecretsV2

from tests.server.fakes import FakeCollection


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


def test_project_create_defaults_archived_false():
    projects = Projects(FakeCollection([]))
    payload, code = projects.create("alpha", "Alpha")
    assert code == 201
    assert payload["archived"] is False


class _DuplicateKeyCollection(FakeCollection):
    def insert_one(self, doc):
        raise DuplicateKeyError("duplicate slug")


def test_project_create_duplicate_key_is_400():
    # The unique slug index raises DuplicateKeyError; the narrowed guard still
    # maps that to a clean 400 (while a connection outage now propagates
    # instead of masquerading as "already exists").
    projects = Projects(_DuplicateKeyCollection([]))
    result, code = projects.create("alpha", "Alpha")
    assert code == 400
    assert result == "Project already exists"


def test_project_update_archives():
    projects = _projects_with("alpha")
    doc, code = projects.update("alpha", archived=True)
    assert code == 200
    assert doc["archived"] is True


def test_project_update_unarchives():
    projects = _projects_with("alpha")
    projects.update("alpha", archived=True)
    doc, code = projects.update("alpha", archived=False)
    assert code == 200
    assert doc["archived"] is False


def test_project_update_no_fields_is_400():
    projects = _projects_with("alpha")
    msg, code = projects.update("alpha")
    assert code == 400
    assert msg == "No fields to update"


def _projects_with_flags(*specs):
    """Build Projects from (slug, archived_or_missing) tuples.

    Passing ``None`` as the flag omits the ``archived`` key entirely, i.e.
    a legacy document that predates the feature.
    """
    docs = []
    for slug, archived in specs:
        doc = {"_id": ObjectId(), "slug": slug, "name": slug.title()}
        if archived is not None:
            doc["archived"] = archived
        docs.append(doc)
    return Projects(FakeCollection(docs))


def test_project_list_excludes_archived_by_default():
    projects = _projects_with_flags(("active", False), ("gone", True))
    result = projects.list()
    assert [p["slug"] for p in result] == ["active"]
    assert result[0]["archived"] is False


def test_project_list_archived_only():
    projects = _projects_with_flags(("active", False), ("gone", True))
    result = projects.list(archived=True)
    assert [p["slug"] for p in result] == ["gone"]
    assert result[0]["archived"] is True


def test_project_list_missing_field_is_active():
    projects = _projects_with_flags(("legacy", None))
    active = projects.list()
    assert [p["slug"] for p in active] == ["legacy"]
    assert active[0]["archived"] is False
    assert projects.list(archived=True) == []


def test_project_list_dual_emits_created_at_camel_and_snake():
    projects = Projects(
        FakeCollection(
            [{"_id": ObjectId(), "slug": "alpha", "created_at": _now()}]
        )
    )
    row = projects.list()[0]
    # camelCase is canonical; snake_case is the deprecated dual-emit twin.
    assert row["createdAt"] == row["created_at"] == "2026-01-01T00:00:00Z"


def test_config_create_dual_emits_created_at_without_storing_camel():
    collection = FakeCollection([])
    configs = Configs(collection)
    payload, code = configs.create("p1", "prod", "Prod")
    assert code == 201
    # Response carries camelCase; the persisted doc stays snake_case only.
    assert payload["createdAt"] == to_iso(payload["created_at"])
    assert "createdAt" not in collection.docs[0]


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


# --------------------------------------------------------------------------
# Descriptions (projects + configs)
# --------------------------------------------------------------------------


def test_project_create_stores_normalized_description():
    projects = Projects(FakeCollection([]))
    payload, code = projects.create("alpha", "Alpha", description="  app  ")
    assert code == 201
    assert payload["description"] == "app"


def test_project_create_blank_description_is_none():
    projects = Projects(FakeCollection([]))
    payload, _ = projects.create("alpha", "Alpha", description="   ")
    assert payload["description"] is None


def test_project_update_persists_and_clears_description():
    projects = _projects_with("alpha")
    doc, code = projects.update("alpha", description="now stored")
    assert code == 200
    assert doc["description"] == "now stored"
    cleared, _ = projects.update("alpha", description="")
    assert cleared["description"] is None


def test_project_list_includes_description():
    projects = _projects_with("alpha")
    projects.update("alpha", description="listed")
    result = projects.list()
    assert result[0]["description"] == "listed"


def test_config_create_stores_normalized_description():
    configs = Configs(FakeCollection([]))
    payload, code = configs.create(
        "p1", "prod", "Prod", description="  live env  "
    )
    assert code == 201
    assert payload["description"] == "live env"


def test_config_create_blank_description_is_none():
    configs = Configs(FakeCollection([]))
    payload, _ = configs.create("p1", "prod", "Prod", description="   ")
    assert payload["description"] is None


def test_config_update_sets_and_clears_description():
    base = _config_doc("prod", "p1")
    configs = Configs(FakeCollection([base]))
    updated, code = configs.update("p1", "prod", description="managed")
    assert code == 200
    assert updated["description"] == "managed"
    cleared, _ = configs.update("p1", "prod", description="")
    assert cleared["description"] is None


def test_config_update_none_description_leaves_it_untouched():
    base = _config_doc("prod", "p1")
    base["description"] = "keep"
    configs = Configs(FakeCollection([base]))
    updated, _ = configs.update("p1", "prod", name="Prod 2")
    assert updated["description"] == "keep"


def test_config_list_includes_description():
    base = _config_doc("prod", "p1")
    base["description"] = "listed"
    configs = Configs(FakeCollection([base]))
    result = configs.list("p1")
    assert result[0]["description"] == "listed"

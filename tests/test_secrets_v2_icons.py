from Engines.secret_icons import resolve_icon_slug
from Engines.secrets_v2 import SecretsV2


class FakeSecrets:
    def __init__(self, docs):
        self.docs = docs

    def create_index(self, *_args, **_kwargs):
        return None

    def _match(self, doc, query):
        for key, value in query.items():
            if isinstance(value, dict) and "$in" in value:
                if doc.get(key) not in value["$in"]:
                    return False
                continue
            if doc.get(key) != value:
                return False
        return True

    def find(self, query, projection=None):
        rows = [doc for doc in self.docs if self._match(doc, query)]
        if not projection:
            return rows
        projected = []
        for doc in rows:
            subset = {}
            for key in projection:
                if key in doc:
                    subset[key] = doc[key]
            projected.append(subset)
        return projected

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if self._match(doc, query):
                if not projection:
                    return doc
                subset = {}
                for key in projection:
                    if key in doc:
                        subset[key] = doc[key]
                return subset
        return None

    def update_one(self, query, update, upsert=False):
        target = None
        for doc in self.docs:
            if self._match(doc, query):
                target = doc
                break

        if target is None:
            if not upsert:
                return None
            target = dict(query)
            self.docs.append(target)

        for key, value in update.get("$set", {}).items():
            target[key] = value

        for key in update.get("$unset", {}):
            target.pop(key, None)

        return None

    def update_many(self, query, update):
        for doc in self.docs:
            if not self._match(doc, query):
                continue
            for key, value in update.get("$set", {}).items():
                doc[key] = value


class FakeConfigs:
    def __init__(self, cfgs):
        self.cfgs = cfgs

    def get_by_id(self, cfg_id):
        return self.cfgs.get(cfg_id)

    def list_ids(self, project_id):
        return [
            cfg["_id"]
            for cfg in self.cfgs.values()
            if cfg.get("project_id") == project_id
        ]


def _engine_with_docs(docs):
    cfgs = {
        "cfg": {"_id": "cfg", "project_id": "p1", "parent_config_id": None}
    }
    return SecretsV2(FakeSecrets(docs), FakeConfigs(cfgs))


def _engine_with_project_docs(docs):
    cfgs = {
        "cfg-a": {
            "_id": "cfg-a",
            "project_id": "p1",
            "parent_config_id": None,
        },
        "cfg-b": {
            "_id": "cfg-b",
            "project_id": "p1",
            "parent_config_id": None,
        },
    }
    return SecretsV2(FakeSecrets(docs), FakeConfigs(cfgs))


def test_put_sets_auto_icon_when_missing():
    engine = _engine_with_docs([])
    _, code = engine.put(
        "cfg", "SQLALCHEMY_DATABASE_URI", "postgres://", "actor"
    )
    assert code == 200
    doc = engine._secrets.docs[0]
    assert doc["icon_slug"] == "simple-icons:sqlalchemy"
    assert doc["icon_source"] == SecretsV2.ICON_SOURCE_AUTO


def test_put_preserves_existing_icon_without_override():
    docs = [
        {
            "config_id": "cfg",
            "key": "DATABASE_URL",
            "value_enc": "v",
            "icon_slug": "simple-icons:postgresql",
        }
    ]
    engine = _engine_with_docs(docs)
    _, code = engine.put("cfg", "DATABASE_URL", "next", "actor")
    assert code == 200
    assert docs[0]["icon_slug"] == "simple-icons:postgresql"


def test_put_accepts_manual_override():
    engine = _engine_with_docs([])
    _, code = engine.put(
        "cfg",
        "DATABASE_URL",
        "postgres://",
        "actor",
        icon_slug="simple-icons:mysql",
        icon_slug_provided=True,
    )
    assert code == 200
    assert engine._secrets.docs[0]["icon_slug"] == "simple-icons:mysql"
    assert (
        engine._secrets.docs[0]["icon_source"] == SecretsV2.ICON_SOURCE_MANUAL
    )


def test_put_empty_override_recomputes_auto_icon():
    docs = [
        {
            "config_id": "cfg",
            "key": "DATABASE_URL",
            "value_enc": "v",
            "icon_slug": "simple-icons:mysql",
        }
    ]
    engine = _engine_with_docs(docs)
    _, code = engine.put(
        "cfg",
        "DATABASE_URL",
        "v2",
        "actor",
        icon_slug="",
        icon_slug_provided=True,
    )
    assert code == 200
    assert docs[0]["icon_slug"] == resolve_icon_slug("DATABASE_URL", None)
    assert docs[0]["icon_source"] == SecretsV2.ICON_SOURCE_AUTO


def test_export_metadata_backfills_missing_icon_slug():
    docs = [
        {
            "_id": "1",
            "config_id": "cfg",
            "key": "SQLALCHEMY_DATABASE_URI",
            "value_enc": "v",
        }
    ]
    engine = _engine_with_docs(docs)
    _, meta, _, code = engine.export_config(
        "cfg", include_parent=True, include_metadata=True
    )
    assert code == 200
    assert docs[0]["icon_slug"] == "simple-icons:sqlalchemy"
    assert (
        meta["SQLALCHEMY_DATABASE_URI"]["iconSlug"]
        == "simple-icons:sqlalchemy"
    )
    assert docs[0]["icon_source"] == SecretsV2.ICON_SOURCE_AUTO


def test_put_syncs_icon_slug_across_project_configs():
    docs = [
        {
            "config_id": "cfg-a",
            "key": "DATABASE_URL",
            "value_enc": "a",
            "icon_slug": "simple-icons:postgresql",
        },
        {
            "config_id": "cfg-b",
            "key": "DATABASE_URL",
            "value_enc": "b",
            "icon_slug": "simple-icons:mysql",
        },
    ]
    engine = _engine_with_project_docs(docs)
    _, code = engine.put(
        "cfg-a",
        "DATABASE_URL",
        "next",
        "actor",
        icon_slug="simple-icons:sqlite",
        icon_slug_provided=True,
    )
    assert code == 200
    assert docs[0]["icon_slug"] == "simple-icons:sqlite"
    assert docs[1]["icon_slug"] == "simple-icons:sqlite"
    assert docs[0]["icon_source"] == SecretsV2.ICON_SOURCE_MANUAL
    assert docs[1]["icon_source"] == SecretsV2.ICON_SOURCE_MANUAL


def test_put_without_override_reuses_existing_project_icon():
    docs = [
        {
            "config_id": "cfg-a",
            "key": "DATABASE_URL",
            "value_enc": "a",
            "icon_slug": "simple-icons:postgresql",
            "icon_source": SecretsV2.ICON_SOURCE_MANUAL,
        },
        {"config_id": "cfg-b", "key": "DATABASE_URL", "value_enc": "b"},
    ]
    engine = _engine_with_project_docs(docs)
    _, code = engine.put("cfg-b", "DATABASE_URL", "updated", "actor")
    assert code == 200
    assert docs[1]["icon_slug"] == "simple-icons:postgresql"
    assert docs[1]["icon_source"] == SecretsV2.ICON_SOURCE_MANUAL


def test_recompute_project_icon_slugs_updates_auto_and_skips_manual():
    docs = [
        {
            "config_id": "cfg-a",
            "key": "DOPPLER_ENVIRONMENT",
            "value_enc": "a",
            "icon_slug": "uiw:environment",
            "icon_source": SecretsV2.ICON_SOURCE_AUTO,
        },
        {
            "config_id": "cfg-b",
            "key": "DOPPLER_ENVIRONMENT",
            "value_enc": "b",
            "icon_slug": "uiw:environment",
            "icon_source": SecretsV2.ICON_SOURCE_AUTO,
        },
        {
            "config_id": "cfg-a",
            "key": "AXIOM_ORG_ID",
            "value_enc": "x",
            "icon_slug": "simple-icons:org",
            "icon_source": SecretsV2.ICON_SOURCE_MANUAL,
        },
        {
            "config_id": "cfg-b",
            "key": "AXIOM_ORG_ID",
            "value_enc": "y",
            "icon_slug": "simple-icons:org",
            "icon_source": SecretsV2.ICON_SOURCE_MANUAL,
        },
        {
            "config_id": "cfg-a",
            "key": "DATABASE_URL",
            "value_enc": "z",
            "icon_slug": "not-a-valid-slug",
        },
    ]
    engine = _engine_with_project_docs(docs)
    summary, msg, code = engine.recompute_project_icon_slugs("p1")
    assert code == 200
    assert msg == "OK"
    assert summary == {
        "configsScanned": 2,
        "keysScanned": 3,
        "keysUpdated": 2,
        "secretsUpdated": 3,
        "keysSkippedManual": 1,
    }
    doppler_slug = resolve_icon_slug("DOPPLER_ENVIRONMENT", None)
    database_slug = resolve_icon_slug("DATABASE_URL", None)
    assert docs[0]["icon_slug"] == doppler_slug
    assert docs[0]["icon_source"] == SecretsV2.ICON_SOURCE_AUTO
    assert docs[1]["icon_slug"] == doppler_slug
    assert docs[1]["icon_source"] == SecretsV2.ICON_SOURCE_AUTO
    assert docs[2]["icon_slug"] == "simple-icons:org"
    assert docs[2]["icon_source"] == SecretsV2.ICON_SOURCE_MANUAL
    assert docs[3]["icon_slug"] == "simple-icons:org"
    assert docs[3]["icon_source"] == SecretsV2.ICON_SOURCE_MANUAL
    assert docs[4]["icon_slug"] == database_slug
    assert docs[4]["icon_source"] == SecretsV2.ICON_SOURCE_AUTO

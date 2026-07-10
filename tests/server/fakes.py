"""Shared in-memory Mongo-collection fakes for ``tests/server/``.

Engines in ``ssm_server`` hold their Mongo collection as constructor-injected
state (see the root ``AGENTS.md`` "Code shape" section), so hermetic engine
tests need an in-memory stand-in for that collection. Before this module
existed, each test file hand-rolled its own ``FakeCollection``/``FakeCursor``
(and, for the ``SecretsV2`` tests, ``FakeSecrets``/``FakeConfigs``) with real
capability drift between copies -- e.g. one ``FakeSecrets`` supported
``$in``/upsert/``update_many`` while a sibling copy supported none of that,
purely because whichever test wrote it first only needed a subset.

These classes are the union of every capability a ``tests/server/`` fake
actually exercised, verified against the real call sites in
``ssm_server/engines`` and ``ssm_server/access`` -- nothing here is
speculative. New server tests must import from here rather than redeclare a
Mongo fake; if a test needs a capability this module doesn't have, extend it
here (once), don't fork a new local copy.

Not every historical fake fits this module: ``test_kv_deprecations.py``'s
``FakeKVCollection`` models the legacy, fully-deprecated KV store's
path-keyed document shape (dotted ``data.<key>`` ``$set``/``$unset``), which
is unlike every other collection here (a flat list of docs) and has exactly
one, frozen consumer -- generalizing this module to cover it would add
complexity for a single deprecated caller, so it stays local. Likewise, an
engine-collaborator stub that mimics another ENGINE's public methods (e.g.
``test_rbac.py``'s ``*Stub`` classes, or ``test_onboarding.py``'s
``FakeUserPass``/``FakeTokens``/``FakeWorkspaces``/``FakeUsers``/
``FakeMemberships``) is a different concern from a raw Mongo collection fake
and does not belong here.
"""

from pymongo.errors import DuplicateKeyError

__all__ = ["FakeCollection", "FakeConfigs", "FakeCursor", "FakeSecrets"]


def _matches(doc, query):
    """Evaluate a MongoDB-style query against a plain dict.

    Covers exactly the operators the engines under test issue: equality,
    ``$in``, ``$gt``/``$gte``, ``$exists``, and the ``$and``/``$or`` logical
    combinators (clauses evaluated recursively).
    """
    for key, condition in query.items():
        if key == "$and":
            if not all(_matches(doc, clause) for clause in condition):
                return False
            continue
        if key == "$or":
            if not any(_matches(doc, clause) for clause in condition):
                return False
            continue
        if not _matches_field(doc, key, condition):
            return False
    return True


def _matches_field(doc, key, condition):
    current = doc.get(key)
    if isinstance(condition, dict):
        if "$in" in condition:
            return current in condition["$in"]
        if "$gte" in condition:
            return _compare(current, condition["$gte"], inclusive=True)
        if "$gt" in condition:
            return _compare(current, condition["$gt"], inclusive=False)
        if "$exists" in condition:
            return (key in doc) == bool(condition["$exists"])
    return current == condition


def _compare(current, target, inclusive):
    if current is None:
        return False
    try:
        return current >= target if inclusive else current > target
    except TypeError:
        # Mixed aware/naive datetimes: fall back to an epoch comparison
        # rather than raising -- a real tz_aware=True Mongo client never
        # produces this mix (see ssm_server/AGENTS.md), but a couple of the
        # original fakes guarded for it defensively, so this fake does too.
        return (
            current.timestamp() >= target.timestamp()
            if inclusive
            else current.timestamp() > target.timestamp()
        )


def _apply_update(doc, update):
    for key, value in update.get("$set", {}).items():
        doc[key] = value
    for key in update.get("$unset", {}):
        doc.pop(key, None)


def _upserted_doc(query, update):
    """Build the doc an upsert creates when nothing matched ``query``.

    Seeds it from ``query``'s plain (non-operator) fields -- mirroring
    Mongo's own upsert-from-query-equality behavior -- then layers the
    update on top.
    """
    created = {
        key: value
        for key, value in query.items()
        if not isinstance(value, dict)
    }
    _apply_update(created, update)
    return created


class FakeCursor:
    """In-memory stand-in for a pymongo ``Cursor``.

    Supports exactly the chaining the engines use: ``.sort(key, direction)``
    (single sort key), ``.skip(n)``, ``.limit(n)``, and iteration. Each
    method mutates ``self.docs`` and returns ``self``, matching pymongo's
    fluent chaining.
    """

    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key, direction=1):
        self.docs.sort(key=lambda item: item.get(key), reverse=direction == -1)
        return self

    def skip(self, amount):
        self.docs = self.docs[amount:]
        return self

    def limit(self, amount):
        self.docs = self.docs[:amount]
        return self

    def __iter__(self):
        return iter(self.docs)


class _DeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class _UpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count
        self.modified_count = matched_count


class FakeCollection:
    """General-purpose in-memory stand-in for a raw pymongo ``Collection``.

    Backs a plain Python list of dicts and implements the subset of the
    driver surface the engines actually call: ``find``/``find_one`` (with
    ``$in``/``$gt``/``$gte``/``$exists``/``$and``/``$or`` query support and
    an accepted-but-unapplied ``projection`` arg, matching every original
    fake but one -- see the module docstring), ``insert_one`` (raising
    ``DuplicateKeyError`` on an ``_id`` collision, matching Mongo's implicit
    unique index on ``_id``), ``update_one``/``update_many`` (``$set``/
    ``$unset``, plus upsert-creates-from-query for ``update_one``),
    ``delete_one``/``delete_many``, ``count_documents``, and a no-op
    ``create_index``.

    ``last_query`` records the most recent ``find``/``delete_one`` query --
    a generic stand-in for the one local fake (``test_memberships.py``) that
    asserted on the query an engine built, rather than on data it returned.
    """

    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.last_query = None

    def create_index(self, *_args, **_kwargs):
        return None

    def find(self, query=None, projection=None):
        _ = projection
        query = query or {}
        self.last_query = query
        return FakeCursor([doc for doc in self.docs if _matches(doc, query)])

    def find_one(self, query, projection=None):
        _ = projection
        for doc in self.docs:
            if _matches(doc, query):
                return doc
        return None

    def insert_one(self, doc):
        doc_id = doc.get("_id") if isinstance(doc, dict) else None
        if doc_id is not None and any(
            existing.get("_id") == doc_id for existing in self.docs
        ):
            raise DuplicateKeyError("duplicate key")
        self.docs.append(doc)

    def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if _matches(doc, query):
                _apply_update(doc, update)
                return _UpdateResult(1)
        if upsert:
            self.docs.append(_upserted_doc(query, update))
        return _UpdateResult(0)

    def update_many(self, query, update):
        matched = 0
        for doc in self.docs:
            if _matches(doc, query):
                _apply_update(doc, update)
                matched += 1
        return _UpdateResult(matched)

    def delete_one(self, query):
        self.last_query = query
        for index, doc in enumerate(self.docs):
            if _matches(doc, query):
                del self.docs[index]
                return _DeleteResult(1)
        return _DeleteResult(0)

    def delete_many(self, query):
        keep = [doc for doc in self.docs if not _matches(doc, query)]
        removed = len(self.docs) - len(keep)
        self.docs = keep
        return _DeleteResult(removed)

    def count_documents(self, query=None):
        query = query or {}
        return sum(1 for doc in self.docs if _matches(doc, query))


class FakeSecrets:
    """In-memory stand-in for the collection ``SecretsV2`` wraps.

    Unlike ``FakeCollection``, ``find`` returns a plain list rather than a
    ``FakeCursor`` -- no ``SecretsV2`` call site chains ``.sort()``/
    ``.limit()`` off a secrets ``find()``; every call site consumes the
    result directly (a for-loop or ``list(...)``).
    """

    def __init__(self, docs):
        self.docs = docs

    def create_index(self, *_args, **_kwargs):
        return None

    def find(self, query, projection=None):
        _ = projection
        return [doc for doc in self.docs if _matches(doc, query)]

    def find_one(self, query, projection=None):
        _ = projection
        for doc in self.docs:
            if _matches(doc, query):
                return doc
        return None

    def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if _matches(doc, query):
                _apply_update(doc, update)
                return None
        if upsert:
            self.docs.append(_upserted_doc(query, update))
        return None

    def update_many(self, query, update):
        for doc in self.docs:
            if _matches(doc, query):
                _apply_update(doc, update)


class FakeConfigs:
    """Dict-backed stand-in for the ``Configs`` engine collaborator that
    ``SecretsV2`` takes as its ``configs_engine``.

    This is not a raw Mongo collection fake -- it mimics the two ``Configs``
    methods ``SecretsV2`` actually calls (``get_by_id`` always;
    ``list_ids`` duck-typed via ``getattr(..., callable)``), keyed on a
    plain ``{config_id: config_doc}`` dict rather than a Mongo query.
    """

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

#!/usr/bin/env python3
import hashlib
import json
from datetime import datetime, timezone

from ssm_server.api.serialization import to_iso
from ssm_server.engines.common import (
    REFERENCE_TOKEN_PATTERN,
    is_valid_env_key,
)
from ssm_server.engines.secret_icons import (
    normalize_icon_slug,
    is_valid_icon_slug,
    resolve_icon_slug,
)

# Per-key env annotation: ``{secret_key: comment_line}``. The comment line
# already carries its leading ``#`` so ``to_env`` emits it verbatim.
EnvAnnotationMap = dict[str, str]


def config_export_etag(
    resolved: dict[str, str], meta: dict | None = None
) -> str:
    """Strong ETag for one export representation.

    Without ``meta`` the tag hashes ONLY the resolved ``{key: value}``
    mapping (keys sorted, stable JSON) -- the value-only representation
    the reloader polls (``include_meta`` off). It is byte-identical
    across ``format``/``raw`` and flips only when a resolved value
    changes, including a value inherited from a parent. WHY value-only
    there: the reloader's ``If-None-Match``/304 divergence check must
    react to VALUE changes alone, so a manual icon / sensitivity /
    description edit must never churn its containers.

    The console requests ``include_meta``/``include_provenance``, so its
    body ALSO carries per-key metadata (icon slug, sensitivity,
    description, ``updatedAt``...). That is a DIFFERENT representation:
    passing ``meta`` folds it into the tag so a metadata-only edit flips
    the tag and the console's conditional refetch is served fresh (200)
    instead of a stale 304 that keeps rendering the old icon. Passing
    ``meta=None`` reproduces the value-only tag byte-for-byte, so the
    reloader path (and the revisions it stores) is unaffected. Pure and
    Mongo-free by design.
    """
    canonical = json.dumps(
        resolved,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    if meta is not None:
        canonical += "\n" + json.dumps(
            meta,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f'"{digest[:16]}"'


class SecretCodec:
    """Encryption stub interface for future KMS integration."""

    @staticmethod
    def encrypt(value: str) -> str:
        return value

    @staticmethod
    def decrypt(value_enc: str) -> str:
        return value_enc


class _ConfigKeyComparisonService:
    def __init__(
        self,
        secrets_col,
        *,
        include_parent,
        include_metadata,
        include_empty,
    ):
        self._secrets = secrets_col
        self._include_parent = include_parent
        self._include_metadata = include_metadata
        self._include_empty = include_empty

    def compare(self, configs, key):
        normalized_configs = self._normalize_configs(configs)
        if not normalized_configs:
            return [], "OK", 200

        config_by_id = {cfg["_id"]: cfg for cfg in normalized_configs}
        direct_by_config_id = self._direct_by_config_id(config_by_id, key)

        rows = []
        for config in normalized_configs:
            row, err, code = self._build_row(
                config, config_by_id, direct_by_config_id
            )
            if err:
                return None, err, code
            if row is not None:
                rows.append(row)
        return rows, "OK", 200

    @staticmethod
    def _normalize_configs(configs):
        normalized = []
        for cfg in configs:
            config_id = cfg.get("_id")
            slug = cfg.get("slug")
            if config_id is None or not isinstance(slug, str):
                continue
            normalized.append(
                {
                    "_id": config_id,
                    "slug": slug,
                    "parent_config_id": cfg.get("parent_config_id"),
                }
            )
        return normalized

    def _direct_by_config_id(self, config_by_id, key):
        config_ids = list(config_by_id.keys())
        direct_docs = list(
            self._secrets.find({"config_id": {"$in": config_ids}, "key": key})
        )
        return {doc["config_id"]: doc for doc in direct_docs}

    def _build_row(self, config, config_by_id, direct_by_config_id):
        direct_doc = direct_by_config_id.get(config["_id"])
        (
            source_config,
            effective_doc,
            is_inherited,
            err,
            code,
        ) = self._resolve_effective_doc(
            config, config_by_id, direct_by_config_id
        )
        if err:
            return None, err, code

        if effective_doc is None and not self._include_empty:
            return None, None, None

        effective_sensitive = self._effective_sensitive(
            config, config_by_id, direct_by_config_id
        )
        row = {
            "configId": str(config["_id"]),
            "configSlug": config["slug"],
            "effective": self._effective_payload(
                effective_doc, source_config, is_inherited, effective_sensitive
            ),
            "direct": self._direct_payload(direct_doc),
        }
        if self._include_metadata:
            row["meta"] = self._meta_payload(effective_doc)
        return row, None, None

    def _resolve_effective_doc(
        self, config, config_by_id, direct_by_config_id
    ):
        direct_doc = direct_by_config_id.get(config["_id"])
        if direct_doc is not None or not self._include_parent:
            return config, direct_doc, False, None, None

        source_config, inherited_doc, err, code = (
            self._find_effective_for_config(
                config, config_by_id, direct_by_config_id
            )
        )
        if err or inherited_doc is None:
            return config, None, False, err, code
        return source_config, inherited_doc, True, None, None

    @staticmethod
    def _find_effective_for_config(config, config_by_id, direct_by_config_id):
        visited = {str(config["_id"])}
        current = config.get("parent_config_id")
        while current is not None:
            current_key = str(current)
            if current_key in visited:
                return None, None, "Config inheritance cycle detected", 400
            visited.add(current_key)

            parent = config_by_id.get(current)
            if parent is None:
                return None, None, None, None
            direct_doc = direct_by_config_id.get(parent["_id"])
            if direct_doc is not None:
                return parent, direct_doc, None, None
            current = parent.get("parent_config_id")
        return None, None, None, None

    @staticmethod
    def _effective_sensitive(config, config_by_id, direct_by_config_id):
        """Most-restrictive-wins sensitivity for a config's effective value.

        Walks config -> parents and returns ``True`` as soon as any doc that
        supplies this key in the chain is sensitive (explicit ``True`` or a
        missing flag, since absence means sensitive). A child can never
        un-hide a key an ancestor marks sensitive. Default ``True`` when no
        doc in the chain holds the key.
        """
        visited = set()
        current = config
        found = False
        while current is not None:
            key_id = str(current["_id"])
            if key_id in visited:
                break
            visited.add(key_id)
            doc = direct_by_config_id.get(current["_id"])
            if doc is not None:
                found = True
                if bool(doc.get("sensitive", True)):
                    return True
            parent_id = current.get("parent_config_id")
            if parent_id is not None and parent_id not in config_by_id:
                # The chain extends beyond the config set we were handed
                # (comparison sets are authorization-filtered and
                # truncated). Fail CLOSED: an unseen ancestor may mark
                # the key sensitive, and a child must never widen
                # exposure just because the ancestor is out of view.
                return True
            current = (
                config_by_id.get(parent_id) if parent_id is not None else None
            )
        return False if found else True

    @staticmethod
    def _effective_payload(
        effective_doc, source_config, is_inherited, sensitive
    ):
        if effective_doc is None:
            return {
                "value": None,
                "source": None,
                "isInherited": False,
                "sensitive": sensitive,
            }
        return {
            "value": SecretCodec.decrypt(effective_doc["value_enc"]),
            "source": source_config["slug"],
            "isInherited": is_inherited,
            "sensitive": sensitive,
        }

    @staticmethod
    def _direct_payload(direct_doc):
        if direct_doc is None:
            return {"exists": False, "value": None}
        return {
            "exists": True,
            "value": SecretCodec.decrypt(direct_doc["value_enc"]),
            "sensitive": bool(direct_doc.get("sensitive", True)),
        }

    @staticmethod
    def _meta_payload(effective_doc):
        if effective_doc is None:
            return {
                "updatedAt": None,
                "updatedBy": None,
                "iconSlug": "",
                "description": "",
            }
        return {
            "updatedAt": to_iso(effective_doc.get("updated_at")),
            "updatedBy": effective_doc.get("updated_by"),
            "iconSlug": normalize_icon_slug(effective_doc.get("icon_slug")),
            "description": effective_doc.get("description") or "",
        }


class _ExportAccumulator:
    """Merge state folded down an inheritance chain (root -> leaf).

    Later configs in the chain override earlier ones, so a single left-to-right
    pass yields child-wins values while accumulating most-restrictive
    sensitivity and last-writer provenance/icon per key.
    """

    def __init__(self, build_meta):
        self._build_meta = build_meta
        self.merged: dict[str, str] = {}
        self.meta: dict[str, dict] = {}
        self.project_icon_by_key: dict[str, str] = {}
        self.keys_needing_sync: set[str] = set()
        self.sensitive_by_key: dict[str, bool] = {}
        self.source_cfg_by_key: dict[str, dict] = {}

    def add(self, cfg, item):
        key = item["key"]
        self.merged[key] = SecretCodec.decrypt(item["value_enc"])
        self.source_cfg_by_key[key] = cfg
        self.sensitive_by_key[key] = self.sensitive_by_key.get(
            key, False
        ) or bool(item.get("sensitive", True))
        icon_slug = self._resolve_icon(key, item)
        if self._build_meta:
            self.meta[key] = {
                "updatedAt": to_iso(item.get("updated_at")),
                "updatedBy": item.get("updated_by"),
                "iconSlug": icon_slug,
                "description": item.get("description") or "",
            }

    def _resolve_icon(self, key, item):
        icon_slug = normalize_icon_slug(item.get("icon_slug"))
        if not is_valid_icon_slug(icon_slug):
            icon_slug = resolve_icon_slug(key, None)
            self.keys_needing_sync.add(key)
        previous_icon_slug = self.project_icon_by_key.get(key)
        if previous_icon_slug and previous_icon_slug != icon_slug:
            self.keys_needing_sync.add(key)
        self.project_icon_by_key[key] = icon_slug
        return icon_slug


class SecretsV2:
    ICON_SOURCE_AUTO = "auto"
    ICON_SOURCE_MANUAL = "manual"

    def __init__(self, secrets_col, configs_engine):
        self._secrets = secrets_col
        self._configs = configs_engine
        self._secrets.create_index([("config_id", 1), ("key", 1)], unique=True)

    @classmethod
    def _normalize_icon_source(cls, value):
        return (
            cls.ICON_SOURCE_MANUAL
            if value == cls.ICON_SOURCE_MANUAL
            else cls.ICON_SOURCE_AUTO
        )

    def _existing_icon_entry(self, config_id, key):
        existing = self._secrets.find_one(
            {"config_id": config_id, "key": key},
            {"icon_slug": 1, "icon_source": 1},
        )
        if not existing:
            return "", self.ICON_SOURCE_AUTO
        return (
            normalize_icon_slug(existing.get("icon_slug")),
            self._normalize_icon_source(existing.get("icon_source")),
        )

    def _project_config_ids_for_config(self, config_id):
        config = self._configs.get_by_id(config_id)
        if not config:
            return [config_id]

        config_id_value = config.get("_id", config_id)
        project_id = config.get("project_id")
        if project_id is None:
            return [config_id_value]

        list_ids = getattr(self._configs, "list_ids", None)
        if callable(list_ids):
            config_ids = list_ids(project_id)
            if config_ids:
                return config_ids

        return [config_id_value]

    def _existing_project_icon_entry(self, config_id, key):
        for current_config_id in self._project_config_ids_for_config(
            config_id
        ):
            icon_slug, icon_source = self._existing_icon_entry(
                current_config_id, key
            )
            if is_valid_icon_slug(icon_slug):
                return icon_slug, icon_source
        return "", self.ICON_SOURCE_AUTO

    def _sync_project_icon_slug(self, config_id, key, icon_slug, icon_source):
        config_ids = self._project_config_ids_for_config(config_id)
        if not config_ids:
            return

        set_doc = {
            "icon_slug": icon_slug,
            "icon_source": self._normalize_icon_source(icon_source),
        }
        update_many = getattr(self._secrets, "update_many", None)
        if callable(update_many):
            update_many(
                {"config_id": {"$in": config_ids}, "key": key},
                {"$set": set_doc},
            )
            return

        for current_config_id in config_ids:
            self._secrets.update_one(
                {"config_id": current_config_id, "key": key},
                {"$set": set_doc},
            )

    def _resolve_icon_slug_for_put(
        self, config_id, key, icon_slug, icon_slug_provided
    ):
        if icon_slug_provided:
            if icon_slug is not None and not isinstance(icon_slug, str):
                return None, None, "Invalid icon slug", 400
            normalized_icon_slug = normalize_icon_slug(icon_slug)
            if normalized_icon_slug and not is_valid_icon_slug(
                normalized_icon_slug
            ):
                return None, None, "Invalid icon slug", 400
            if normalized_icon_slug:
                return (
                    normalized_icon_slug,
                    self.ICON_SOURCE_MANUAL,
                    None,
                    None,
                )
            return (
                resolve_icon_slug(key, None),
                self.ICON_SOURCE_AUTO,
                None,
                None,
            )

        existing_project_icon_slug, existing_icon_source = (
            self._existing_project_icon_entry(config_id, key)
        )
        if is_valid_icon_slug(existing_project_icon_slug):
            return existing_project_icon_slug, existing_icon_source, None, None
        return (
            resolve_icon_slug(key, None),
            self.ICON_SOURCE_AUTO,
            None,
            None,
        )

    def recompute_project_icon_slugs(self, project_id):
        list_ids = getattr(self._configs, "list_ids", None)
        if not callable(list_ids):
            return None, "Config list lookup is unavailable", 500

        config_ids = list_ids(project_id) or []
        summary = {
            "configsScanned": len(config_ids),
            "keysScanned": 0,
            "keysUpdated": 0,
            "secretsUpdated": 0,
            "keysSkippedManual": 0,
        }
        if not config_ids:
            return summary, "OK", 200

        docs = list(
            self._secrets.find(
                {"config_id": {"$in": config_ids}},
                {"config_id": 1, "key": 1, "icon_slug": 1, "icon_source": 1},
            )
        )
        docs_by_key = {}
        for doc in docs:
            key = doc.get("key")
            if not isinstance(key, str):
                continue
            docs_by_key.setdefault(key, []).append(doc)

        for key, key_docs in docs_by_key.items():
            summary["keysScanned"] += 1
            has_manual = any(
                self._normalize_icon_source(doc.get("icon_source"))
                == self.ICON_SOURCE_MANUAL
                for doc in key_docs
            )
            if has_manual:
                summary["keysSkippedManual"] += 1
                continue

            desired_slug = resolve_icon_slug(key, None)
            needs_update = any(
                normalize_icon_slug(doc.get("icon_slug")) != desired_slug
                or self._normalize_icon_source(doc.get("icon_source"))
                != self.ICON_SOURCE_AUTO
                for doc in key_docs
            )
            if not needs_update:
                continue

            summary["keysUpdated"] += 1
            summary["secretsUpdated"] += len(key_docs)

            update_many = getattr(self._secrets, "update_many", None)
            if callable(update_many):
                update_many(
                    {"config_id": {"$in": config_ids}, "key": key},
                    {
                        "$set": {
                            "icon_slug": desired_slug,
                            "icon_source": self.ICON_SOURCE_AUTO,
                        }
                    },
                )
                continue

            for config_id in config_ids:
                self._secrets.update_one(
                    {"config_id": config_id, "key": key},
                    {
                        "$set": {
                            "icon_slug": desired_slug,
                            "icon_source": self.ICON_SOURCE_AUTO,
                        }
                    },
                )

        return summary, "OK", 200

    def _resolve_sensitive_for_put(
        self, config_id, key, sensitive, sensitive_provided
    ):
        """Resolve the ``sensitive`` flag a put should persist.

        Explicit value wins. When omitted, an existing doc's flag is
        preserved (never reset) and a fresh key defaults to sensitive --
        absence of the field always reads as sensitive elsewhere.
        """
        if sensitive_provided:
            if not isinstance(sensitive, bool):
                return None, "sensitive must be a boolean", 400
            return sensitive, None, None
        existing = self._secrets.find_one(
            {"config_id": config_id, "key": key}, {"sensitive": 1}
        )
        if existing is None:
            return True, None, None
        return bool(existing.get("sensitive", True)), None, None

    def _resolve_description_for_put(
        self, config_id, key, description, description_provided
    ):
        """Resolve the free-text ``description`` a put should persist.

        Explicit value wins (an empty string clears it). When omitted, an
        existing doc's description is preserved -- so an icon/value/
        sensitivity edit never wipes the annotation -- and a fresh key
        defaults to no description. Description is metadata: it lives only
        in ``meta`` and never enters the value map, so it can't flip the
        value-only export ETag the reloader polls.
        """
        if description_provided:
            if description is not None and not isinstance(description, str):
                return None, "description must be a string", 400
            return (description or ""), None, None
        existing = self._secrets.find_one(
            {"config_id": config_id, "key": key}, {"description": 1}
        )
        if existing is None:
            return "", None, None
        return (existing.get("description") or ""), None, None

    def put(
        self,
        config_id,
        key,
        value,
        actor,
        icon_slug=None,
        icon_slug_provided=False,
        sensitive=None,
        sensitive_provided=False,
        description=None,
        description_provided=False,
    ):
        if not is_valid_env_key(key):
            return "Invalid secret key", 400
        if not isinstance(value, str):
            return "Secret value must be a string", 400
        (
            resolved_icon_slug,
            resolved_icon_source,
            err,
            code,
        ) = self._resolve_icon_slug_for_put(
            config_id, key, icon_slug, icon_slug_provided
        )
        if err:
            return err, code
        resolved_sensitive, err, code = self._resolve_sensitive_for_put(
            config_id, key, sensitive, sensitive_provided
        )
        if err:
            return err, code
        resolved_description, err, code = self._resolve_description_for_put(
            config_id, key, description, description_provided
        )
        if err:
            return err, code

        update_doc = {
            "$set": {
                "value_enc": SecretCodec.encrypt(value),
                "updated_at": datetime.now(timezone.utc),
                "updated_by": actor,
                "icon_slug": resolved_icon_slug,
                "icon_source": resolved_icon_source,
                "sensitive": resolved_sensitive,
                "description": resolved_description,
            }
        }

        self._secrets.update_one(
            {"config_id": config_id, "key": key}, update_doc, upsert=True
        )
        self._sync_project_icon_slug(
            config_id, key, resolved_icon_slug, resolved_icon_source
        )
        return {
            "status": "OK",
            "key": key,
            "sensitive": resolved_sensitive,
        }, 200

    def _chain_effective_sensitive(self, config_id, key: str) -> bool:
        """Most-restrictive-wins sensitivity over the FULL DB chain.

        Unlike the comparison service (which only sees an
        authorization-filtered config set), this walks the real parent
        chain, so every read surface reports the same effective flag as
        the export meta. Fail-closed: chain-resolution errors read as
        sensitive.
        """
        chain, err, _code = self._resolve_chain(config_id)
        if err or not chain:
            return True
        docs = self._secrets.find(
            {"config_id": {"$in": [c["_id"] for c in chain]}, "key": key}
        )
        found = False
        for doc in docs:
            found = True
            if bool(doc.get("sensitive", True)):
                return True
        return False if found else True

    def get(self, config_id, key):
        if not is_valid_env_key(key):
            return "Invalid secret key", 400
        doc = self._secrets.find_one({"config_id": config_id, "key": key})
        if not doc:
            return "Secret not found", 404
        return {
            "key": key,
            "value": SecretCodec.decrypt(doc["value_enc"]),
            "sensitive": self._chain_effective_sensitive(config_id, key),
            "status": "OK",
        }, 200

    def delete(self, config_id, key):
        if not is_valid_env_key(key):
            return "Invalid secret key", 400
        res = self._secrets.delete_one({"config_id": config_id, "key": key})
        if res.deleted_count == 0:
            return "Secret not found", 404
        return {"status": "OK", "key": key}, 200

    def delete_by_config(self, config_id):
        """Purge every secret stored under a single config."""
        res = self._secrets.delete_many({"config_id": config_id})
        return res.deleted_count

    def delete_by_configs(self, config_ids):
        """Purge every secret stored under any of ``config_ids``."""
        config_ids = list(config_ids or [])
        if not config_ids:
            return 0
        res = self._secrets.delete_many({"config_id": {"$in": config_ids}})
        return res.deleted_count

    def compare_key_across_configs(
        self,
        configs,
        key,
        include_parent=True,
        include_metadata=True,
        include_empty=True,
    ):
        if not is_valid_env_key(key):
            return None, "Invalid secret key", 400
        comparator = _ConfigKeyComparisonService(
            self._secrets,
            include_parent=include_parent,
            include_metadata=include_metadata,
            include_empty=include_empty,
        )
        return comparator.compare(configs, key)

    def _resolve_chain(self, config_id):
        chain = []
        visited = set()
        current = config_id
        while current is not None:
            if str(current) in visited:
                return None, "Config inheritance cycle detected", 400
            visited.add(str(current))
            cfg = self._configs.get_by_id(current)
            if cfg is None:
                return None, "Config not found", 404
            chain.append(cfg)
            current = cfg.get("parent_config_id")
        chain.reverse()
        return chain, None, None

    def export_config(
        self,
        config_id,
        include_parent=True,
        include_metadata=False,
        include_provenance=False,
    ):
        """Merge a config's secrets down its inheritance chain.

        ``include_metadata`` adds per-key ``updatedAt``/``updatedBy``/
        ``iconSlug``/``sensitive``. ``include_provenance`` additionally tags
        each key with ``source`` (the config slug that supplied the effective
        value) and ``isInherited``. Provenance and sensitivity live only in
        ``meta`` -- the merged value map (which feeds ``config_export_etag``)
        never carries them, so opting in never flips the ETag.
        """
        chain = [self._configs.get_by_id(config_id)]
        if chain[0] is None:
            return None, None, "Config not found", 404
        if include_parent:
            chain, err, code = self._resolve_chain(config_id)
            if err:
                return None, None, err, code
        build_meta = include_metadata or include_provenance
        acc = _ExportAccumulator(build_meta)
        for cfg in chain:
            for item in self._secrets.find({"config_id": cfg["_id"]}):
                acc.add(cfg, item)

        if build_meta:
            self._enrich_meta(
                acc.meta,
                config_id=config_id,
                include_metadata=include_metadata,
                include_provenance=include_provenance,
                sensitive_by_key=acc.sensitive_by_key,
                source_cfg_by_key=acc.source_cfg_by_key,
            )

        for key in acc.keys_needing_sync:
            self._sync_project_icon_slug(
                config_id,
                key,
                acc.project_icon_by_key[key],
                self.ICON_SOURCE_AUTO,
            )
        return acc.merged, acc.meta if build_meta else None, "OK", 200

    @staticmethod
    def _enrich_meta(
        meta,
        *,
        config_id,
        include_metadata,
        include_provenance,
        sensitive_by_key,
        source_cfg_by_key,
    ):
        for key, entry in meta.items():
            if include_metadata:
                entry["sensitive"] = sensitive_by_key.get(key, True)
            if include_provenance:
                source_cfg = source_cfg_by_key.get(key)
                entry["source"] = (
                    source_cfg.get("slug") if source_cfg else None
                )
                entry["isInherited"] = bool(
                    source_cfg is not None
                    and source_cfg.get("_id") != config_id
                )

    def find_configs_referencing(
        self,
        deleted_config_id,
        project_slug,
        config_slug,
        same_project_config_ids,
    ):
        """Config ids whose values reference ``project_slug/config_slug``.

        Reference forms (see ``references.py``): a same-project ``${cfg.KEY}``
        counts only for secrets inside the deleted config's project; a
        fully-qualified ``${proj.cfg.KEY}`` counts from anywhere. The deleted
        config's own secrets are ignored (they vanish with it). Used by the
        delete path to block dangling references before removal.
        """
        same_project = set(same_project_config_ids or [])
        referencing: set = set()
        for doc in self._secrets.find({}):
            source_config_id = doc.get("config_id")
            if source_config_id == deleted_config_id:
                continue
            value = SecretCodec.decrypt(doc.get("value_enc", ""))
            if "${" not in value:
                continue
            if self._value_references_config(
                value,
                project_slug,
                config_slug,
                source_config_id in same_project,
            ):
                referencing.add(source_config_id)
        return referencing

    @staticmethod
    def _value_references_config(
        value, project_slug, config_slug, source_in_project
    ):
        for match in REFERENCE_TOKEN_PATTERN.finditer(value):
            parts = match.group(1).strip().split(".")
            if len(parts) == 3:
                ref_project, ref_config, _key = parts
                if ref_project == project_slug and ref_config == config_slug:
                    return True
            elif len(parts) == 2 and source_in_project:
                ref_config, _key = parts
                if ref_config == config_slug:
                    return True
        return False

    @staticmethod
    def to_env(data, annotations: EnvAnnotationMap | None = None):
        """Render ``{key: value}`` as ``KEY=value`` lines.

        ``annotations`` optionally maps a key to a comment line emitted above
        it (used for ``# from <config>`` provenance). Omitting it keeps the
        output byte-identical to the annotation-free form.
        """
        annotations = annotations or {}
        lines = []
        for key, value in data.items():
            if "\n" in value:
                return (
                    None,
                    f"Value for {key} contains newline; "
                    "env format does not support it",
                    400,
                )
            comment = annotations.get(key)
            if comment:
                # Annotations embed operator-editable text (config
                # descriptions); flatten CR and LF so a crafted
                # description can never smuggle a non-comment line into
                # the rendered .env (mirrors the value newline guard).
                flat = comment.replace("\r", " ").replace("\n", " ")
                lines.append(flat)
            lines.append(f"{key}={value}")
        return "\n".join(lines), "OK", 200

#!/usr/bin/env python3
from datetime import datetime, timezone

from Api.serialization import to_iso
from Engines.common import is_valid_env_key
from Engines.secret_icons import (
    normalize_icon_slug,
    is_valid_icon_slug,
    resolve_icon_slug,
)


class SecretCodec:
    """Encryption stub interface for future KMS integration."""

    @staticmethod
    def encrypt(value: str) -> str:
        return value

    @staticmethod
    def decrypt(value_enc: str) -> str:
        return value_enc


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

    def put(
        self,
        config_id,
        key,
        value,
        actor,
        icon_slug=None,
        icon_slug_provided=False,
    ):
        if not is_valid_env_key(key):
            return "Invalid secret key", 400
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

        update_doc = {
            "$set": {
                "value_enc": SecretCodec.encrypt(value),
                "updated_at": datetime.now(timezone.utc),
                "updated_by": actor,
                "icon_slug": resolved_icon_slug,
                "icon_source": resolved_icon_source,
            }
        }

        self._secrets.update_one(
            {"config_id": config_id, "key": key}, update_doc, upsert=True
        )
        self._sync_project_icon_slug(
            config_id, key, resolved_icon_slug, resolved_icon_source
        )
        return {"status": "OK", "key": key}, 200

    def get(self, config_id, key):
        if not is_valid_env_key(key):
            return "Invalid secret key", 400
        doc = self._secrets.find_one({"config_id": config_id, "key": key})
        if not doc:
            return "Secret not found", 404
        return {
            "key": key,
            "value": SecretCodec.decrypt(doc["value_enc"]),
            "status": "OK",
        }, 200

    def delete(self, config_id, key):
        if not is_valid_env_key(key):
            return "Invalid secret key", 400
        res = self._secrets.delete_one({"config_id": config_id, "key": key})
        if res.deleted_count == 0:
            return "Secret not found", 404
        return {"status": "OK", "key": key}, 200

    @staticmethod
    def _normalize_compare_configs(configs):
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

        normalized_configs = self._normalize_compare_configs(configs)
        if not normalized_configs:
            return [], "OK", 200

        config_by_id = {cfg["_id"]: cfg for cfg in normalized_configs}
        config_ids = list(config_by_id.keys())
        direct_docs = list(
            self._secrets.find({"config_id": {"$in": config_ids}, "key": key})
        )
        direct_by_config_id = {doc["config_id"]: doc for doc in direct_docs}

        rows = []
        for config in normalized_configs:
            config_id = config["_id"]
            direct_doc = direct_by_config_id.get(config_id)
            effective_doc = direct_doc
            source_config = config
            is_inherited = False

            if effective_doc is None and include_parent:
                inherited_source, inherited_doc, err, code = (
                    self._find_effective_for_config(
                        config, config_by_id, direct_by_config_id
                    )
                )
                if err:
                    return None, err, code
                if inherited_doc is not None:
                    source_config = inherited_source
                    effective_doc = inherited_doc
                    is_inherited = True

            if effective_doc is None and not include_empty:
                continue

            row = {
                "configId": str(config_id),
                "configSlug": config["slug"],
                "effective": {
                    "value": SecretCodec.decrypt(effective_doc["value_enc"])
                    if effective_doc is not None
                    else None,
                    "source": source_config["slug"]
                    if effective_doc is not None
                    else None,
                    "isInherited": is_inherited
                    if effective_doc is not None
                    else False,
                },
                "direct": {
                    "exists": direct_doc is not None,
                    "value": SecretCodec.decrypt(direct_doc["value_enc"])
                    if direct_doc is not None
                    else None,
                },
            }
            if include_metadata:
                row["meta"] = {
                    "updatedAt": to_iso(effective_doc.get("updated_at"))
                    if effective_doc is not None
                    else None,
                    "updatedBy": effective_doc.get("updated_by")
                    if effective_doc is not None
                    else None,
                    "iconSlug": (
                        normalize_icon_slug(effective_doc.get("icon_slug"))
                        if effective_doc is not None
                        else ""
                    ),
                }
            rows.append(row)
        return rows, "OK", 200

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
        self, config_id, include_parent=True, include_metadata=False
    ):
        chain = [self._configs.get_by_id(config_id)]
        if chain[0] is None:
            return None, None, "Config not found", 404
        if include_parent:
            chain, err, code = self._resolve_chain(config_id)
            if err:
                return None, None, err, code
        merged = {}
        meta = {}
        project_icon_by_key = {}
        keys_needing_sync = set()
        for cfg in chain:
            cursor = self._secrets.find({"config_id": cfg["_id"]})
            for item in cursor:
                merged[item["key"]] = SecretCodec.decrypt(item["value_enc"])
                key = item["key"]
                icon_slug = normalize_icon_slug(item.get("icon_slug"))
                if not is_valid_icon_slug(icon_slug):
                    icon_slug = resolve_icon_slug(key, None)
                    keys_needing_sync.add(key)

                previous_icon_slug = project_icon_by_key.get(key)
                if previous_icon_slug and previous_icon_slug != icon_slug:
                    keys_needing_sync.add(key)
                project_icon_by_key[key] = icon_slug

                if include_metadata:
                    meta[key] = {
                        "updatedAt": to_iso(item.get("updated_at")),
                        "updatedBy": item.get("updated_by"),
                        "iconSlug": icon_slug,
                    }

        for key in keys_needing_sync:
            self._sync_project_icon_slug(
                config_id,
                key,
                project_icon_by_key[key],
                self.ICON_SOURCE_AUTO,
            )
        return merged, meta if include_metadata else None, "OK", 200

    @staticmethod
    def to_env(data):
        lines = []
        for key, value in data.items():
            if "\n" in value:
                return (
                    None,
                    f"Value for {key} contains newline; "
                    "env format does not support it",
                    400,
                )
            lines.append(f"{key}={value}")
        return "\n".join(lines), "OK", 200

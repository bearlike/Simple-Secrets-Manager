#!/usr/bin/env python3
from datetime import datetime, timezone

from Api.serialization import to_iso
from Engines.common import is_valid_env_key


class SecretCodec:
    """Encryption stub interface for future KMS integration."""

    @staticmethod
    def encrypt(value: str) -> str:
        return value

    @staticmethod
    def decrypt(value_enc: str) -> str:
        return value_enc


class SecretsV2:
    def __init__(self, secrets_col, configs_engine):
        self._secrets = secrets_col
        self._configs = configs_engine
        self._secrets.create_index([("config_id", 1), ("key", 1)], unique=True)

    def put(self, config_id, key, value, actor):
        if not is_valid_env_key(key):
            return "Invalid secret key", 400
        self._secrets.update_one(
            {"config_id": config_id, "key": key},
            {
                "$set": {
                    "value_enc": SecretCodec.encrypt(value),
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": actor,
                }
            },
            upsert=True,
        )
        return {"status": "OK", "key": key}, 200

    def get(self, config_id, key):
        if not is_valid_env_key(key):
            return "Invalid secret key", 400
        doc = self._secrets.find_one({"config_id": config_id, "key": key})
        if not doc:
            return "Secret not found", 404
        return {"key": key, "value": SecretCodec.decrypt(doc["value_enc"]), "status": "OK"}, 200

    def delete(self, config_id, key):
        if not is_valid_env_key(key):
            return "Invalid secret key", 400
        res = self._secrets.delete_one({"config_id": config_id, "key": key})
        if res.deleted_count == 0:
            return "Secret not found", 404
        return {"status": "OK", "key": key}, 200

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

    def export_config(self, config_id, include_parent=True, include_metadata=False):
        chain = [self._configs.get_by_id(config_id)]
        if chain[0] is None:
            return None, None, "Config not found", 404
        if include_parent:
            chain, err, code = self._resolve_chain(config_id)
            if err:
                return None, None, err, code
        merged = {}
        meta = {}
        for cfg in chain:
            cursor = self._secrets.find({"config_id": cfg["_id"]})
            for item in cursor:
                merged[item["key"]] = SecretCodec.decrypt(item["value_enc"])
                if include_metadata:
                    meta[item["key"]] = {
                        "updatedAt": to_iso(item.get("updated_at")),
                        "updatedBy": item.get("updated_by"),
                    }
        return merged, meta if include_metadata else None, "OK", 200

    @staticmethod
    def to_env(data):
        lines = []
        for key, value in data.items():
            if "\n" in value:
                return None, f"Value for {key} contains newline; env format does not support it", 400
            lines.append(f"{key}={value}")
        return "\n".join(lines), "OK", 200

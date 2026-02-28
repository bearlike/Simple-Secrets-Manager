from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from ssm_cli.config import cache_root


def _cache_file(base_url: str, project: str, config: str) -> Path:
    identity = f"{base_url}|{project}|{config}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return cache_root() / "secrets" / f"{digest}.json"


def save_secret_cache(
    base_url: str, project: str, config: str, data: dict[str, str]
) -> None:
    path = _cache_file(base_url, project, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"fetched_at": int(time.time()), "data": data}
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True)
        handle.write("\n")
    temp.replace(path)


def load_secret_cache(
    base_url: str,
    project: str,
    config: str,
    max_age_seconds: int | None = None,
) -> dict[str, str] | None:
    path = _cache_file(base_url, project, config)
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        return None

    fetched_at = payload.get("fetched_at")
    data = payload.get("data")
    if not isinstance(fetched_at, int) or not isinstance(data, dict):
        return None

    if max_age_seconds is not None:
        age = int(time.time()) - fetched_at
        if age > max_age_seconds:
            return None

    parsed: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, str):
            parsed[key] = value
    return parsed

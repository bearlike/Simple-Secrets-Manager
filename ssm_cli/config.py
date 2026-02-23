from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_PROFILE = "default"


def global_config_path() -> Path:
    override = os.getenv("SSM_GLOBAL_CONFIG_FILE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "ssm" / "config.json"


def local_config_path(cwd: Path | None = None) -> Path:
    override = os.getenv("SSM_LOCAL_CONFIG_FILE")
    if override:
        return Path(override).expanduser()
    base = cwd or Path.cwd()
    return base / ".ssm" / "config.json"


def credentials_path() -> Path:
    override = os.getenv("SSM_CREDENTIALS_FILE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "ssm" / "credentials.json"


def cache_root() -> Path:
    override = os.getenv("SSM_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "ssm"


@dataclass
class ProfileConfig:
    base_url: str | None = None
    project: str | None = None
    config: str | None = None


@dataclass
class GlobalConfig:
    base_url: str | None = None
    active_profile: str = DEFAULT_PROFILE
    profiles: dict[str, ProfileConfig] = field(default_factory=dict)


@dataclass
class LocalConfig:
    profile: str | None = None
    project: str | None = None
    config: str | None = None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {}
    return data


def _atomic_write_json(path: Path, data: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(temp, mode)
    temp.replace(path)


def load_global_config() -> GlobalConfig:
    raw = _read_json(global_config_path())
    profiles_raw_obj = raw.get("profiles")
    profiles_raw = profiles_raw_obj if isinstance(profiles_raw_obj, dict) else {}
    profiles: dict[str, ProfileConfig] = {}
    for name, value in profiles_raw.items():
        if not isinstance(name, str) or not isinstance(value, dict):
            continue
        profiles[name] = ProfileConfig(
            base_url=_str_or_none(value.get("base_url")),
            project=_str_or_none(value.get("project")),
            config=_str_or_none(value.get("config")),
        )

    active_profile = _str_or_none(raw.get("active_profile")) or DEFAULT_PROFILE
    if active_profile not in profiles:
        profiles[active_profile] = ProfileConfig()

    return GlobalConfig(
        base_url=_str_or_none(raw.get("base_url")),
        active_profile=active_profile,
        profiles=profiles,
    )


def save_global_config(cfg: GlobalConfig) -> None:
    raw_profiles: dict[str, dict[str, str]] = {}
    for name, profile in cfg.profiles.items():
        if not name:
            continue
        item: dict[str, str] = {}
        if profile.base_url:
            item["base_url"] = profile.base_url
        if profile.project:
            item["project"] = profile.project
        if profile.config:
            item["config"] = profile.config
        raw_profiles[name] = item

    payload: dict[str, Any] = {
        "active_profile": cfg.active_profile or DEFAULT_PROFILE,
        "profiles": raw_profiles,
    }
    if cfg.base_url:
        payload["base_url"] = cfg.base_url

    _atomic_write_json(global_config_path(), payload, mode=0o600)


def load_local_config(cwd: Path | None = None) -> LocalConfig:
    raw = _read_json(local_config_path(cwd))
    return LocalConfig(
        profile=_str_or_none(raw.get("profile")),
        project=_str_or_none(raw.get("project")),
        config=_str_or_none(raw.get("config")),
    )


def save_local_config(cfg: LocalConfig, cwd: Path | None = None) -> None:
    payload: dict[str, str] = {}
    if cfg.profile:
        payload["profile"] = cfg.profile
    if cfg.project:
        payload["project"] = cfg.project
    if cfg.config:
        payload["config"] = cfg.config
    _atomic_write_json(local_config_path(cwd), payload, mode=0o600)


def load_credentials() -> dict[str, str]:
    raw = _read_json(credentials_path())
    tokens = raw.get("tokens")
    if not isinstance(tokens, dict):
        return {}
    parsed: dict[str, str] = {}
    for key, value in tokens.items():
        if isinstance(key, str) and isinstance(value, str):
            parsed[key] = value
    return parsed


def save_credentials(tokens: dict[str, str]) -> None:
    _atomic_write_json(credentials_path(), {"tokens": tokens}, mode=0o600)


def _str_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return None

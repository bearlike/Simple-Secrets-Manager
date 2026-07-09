#!/usr/bin/env python3
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

VERSION_FILE_NAME = "VERSION"
PACKAGE_NAME_CANDIDATES = ("simple-secrets-manager", "simple_secrets_manager")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_version_file(path: Optional[Path] = None) -> Optional[str]:
    version_path = path or (_repo_root() / VERSION_FILE_NAME)
    if not version_path.exists():
        return None
    value = version_path.read_text(encoding="utf-8").strip()
    return value or None


def get_application_version() -> str:
    for package_name in PACKAGE_NAME_CANDIDATES:
        try:
            return version(package_name)
        except PackageNotFoundError:
            continue

    fallback = read_version_file()
    if fallback:
        return fallback
    return "unknown"

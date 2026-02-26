#!/usr/bin/env python3
from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional


def _read_pyproject_version(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    in_project = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_project = line == "[project]"
            continue
        if not in_project:
            continue
        match = re.match(r'version\s*=\s*"([^"]+)"', line)
        if match:
            return match.group(1)
    return None


def get_application_version() -> str:
    candidates = ("simple-secrets-manager", "simple_secrets_manager")
    for package_name in candidates:
        try:
            return version(package_name)
        except PackageNotFoundError:
            continue

    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    fallback = _read_pyproject_version(pyproject_path)
    if fallback:
        return fallback
    return "unknown"

"""Simple Secrets Manager CLI package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

__all__ = ["__version__"]


def _read_repo_version() -> str | None:
    version_file = Path(__file__).resolve().parents[1] / "VERSION"
    if not version_file.exists():
        return None
    value = version_file.read_text(encoding="utf-8").strip()
    return value or None


def _resolve_version() -> str:
    for package_name in ("simple-secrets-manager", "simple_secrets_manager"):
        try:
            return version(package_name)
        except PackageNotFoundError:
            continue
    return _read_repo_version() or "unknown"


__version__ = _resolve_version()

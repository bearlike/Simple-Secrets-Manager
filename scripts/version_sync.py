#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_version(root: Path) -> str:
    version_path = root / "VERSION"
    if not version_path.exists():
        raise ValueError("VERSION file is missing")
    version_value = version_path.read_text(encoding="utf-8").strip()
    if not SEMVER_PATTERN.fullmatch(version_value):
        raise ValueError(f"VERSION must match X.Y.Z; got: {version_value!r}")
    return version_value


def run_check(root: Path) -> int:
    errors: list[str] = []
    try:
        _ = read_version(root)
    except ValueError as exc:
        errors.append(str(exc))

    pyproject = _read(root / "pyproject.toml")
    if 'dynamic = ["version"]' not in pyproject:
        errors.append('pyproject.toml must declare [project].dynamic = ["version"]')
    if 'version = { attr = "ssm_cli.__version__" }' not in pyproject:
        errors.append("pyproject.toml must declare [tool.setuptools.dynamic] version attr")
    if re.search(r"(?m)^version\s*=\s*\"[^\"]+\"\\s*$", pyproject):
        errors.append("pyproject.toml still contains a static version assignment")

    cli_init = _read(root / "ssm_cli" / "__init__.py")
    if "VERSION" not in cli_init or "__version__ = _resolve_version()" not in cli_init:
        errors.append("ssm_cli/__init__.py must derive __version__ from VERSION via _resolve_version()")

    dockerfile = _read(root / "Dockerfile")
    if "ARG APP_VERSION" not in dockerfile:
        errors.append("Dockerfile must declare ARG APP_VERSION")
    if 'org.opencontainers.image.version="${APP_VERSION}"' not in dockerfile:
        errors.append("Dockerfile must label org.opencontainers.image.version from APP_VERSION")

    if errors:
        print("version sync check failed:")
        for item in errors:
            print(f"- {item}")
        return 1
    print("version sync check passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and export repository version from VERSION file.")
    parser.add_argument("--check", action="store_true", help="Validate version wiring across the repository.")
    parser.add_argument("--print", action="store_true", help="Print the VERSION value.")
    parser.add_argument(
        "--github-output",
        default=None,
        help="Path to GITHUB_OUTPUT file; writes 'version=<VERSION>' when provided.",
    )
    args = parser.parse_args()

    root = _repo_root()

    try:
        version_value = read_version(root)
    except ValueError as exc:
        print(str(exc))
        return 1

    if args.github_output:
        output_path = Path(args.github_output)
        with output_path.open("a", encoding="utf-8") as handle:
            handle.write(f"version={version_value}\n")

    if args.print:
        print(version_value)

    if args.check:
        return run_check(root)

    if not args.print and not args.github_output:
        print(version_value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

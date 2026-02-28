#!/usr/bin/env python3
"""Build a deterministic Iconify term index for secret icon resolution."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Dict, Iterable, Tuple

import requests  # type: ignore[import-untyped]

ICONIFY_BASE_URL = "https://api.iconify.design"
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _fetch_json(session: requests.Session, endpoint: str) -> dict:
    response = session.get(f"{ICONIFY_BASE_URL}{endpoint}", timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"Unexpected payload for {endpoint}")
    return payload


def _extract_terms(icon_name: str) -> Iterable[str]:
    icon_name = icon_name.lower()
    if not icon_name:
        return []
    tokens = TOKEN_PATTERN.findall(icon_name)
    terms = {icon_name}
    terms.update(token for token in tokens if len(token) >= 3 and not token.isdigit())
    compact = "".join(tokens)
    if len(compact) >= 5:
        terms.add(compact)
    return terms


def _rank(prefix: str, icon_name: str, term: str, slug: str) -> Tuple[int, int, int, str]:
    return (
        1 if prefix == "simple-icons" else 0,
        1 if icon_name == term else 0,
        -len(icon_name),
        slug,
    )


def build_index() -> dict:
    session = requests.Session()
    session.headers.update({"User-Agent": "simple-secrets-manager-icon-index/1.0"})

    collections = _fetch_json(session, "/collections")
    prefixes = sorted(prefix for prefix, details in collections.items() if isinstance(details, dict))

    term_best: Dict[str, Tuple[Tuple[int, int, int, str], str]] = {}
    term_count: Dict[str, int] = {}

    for prefix in prefixes:
        collection = _fetch_json(session, f"/collection?prefix={prefix}")
        icons = list(collection.get("uncategorized") or [])
        aliases = collection.get("aliases")
        if isinstance(aliases, dict):
            icons.extend(aliases.keys())

        for icon_name_raw in icons:
            if not isinstance(icon_name_raw, str):
                continue
            icon_name = icon_name_raw.lower()
            slug = f"{prefix}:{icon_name}"
            for term in _extract_terms(icon_name):
                term_count[term] = term_count.get(term, 0) + 1
                ranked = _rank(prefix, icon_name, term, slug)
                current = term_best.get(term)
                if current is None or ranked > current[0]:
                    term_best[term] = (ranked, slug)

    terms = {
        term: {"slug": value[1], "count": term_count[term]}
        for term, value in sorted(term_best.items(), key=lambda item: item[0])
    }
    return {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": ICONIFY_BASE_URL,
        "terms": terms,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build icon lookup index")
    parser.add_argument(
        "--output",
        default="Engines/icon_index.json",
        help="Path to write the generated index JSON",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    payload = build_index()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(f"Wrote icon index to {output_path} ({len(payload['terms'])} terms)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

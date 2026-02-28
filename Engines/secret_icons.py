#!/usr/bin/env python3
"""Deterministic icon resolution for secret keys using a precomputed index."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Dict, Iterable, Optional, Tuple

DEFAULT_ICON_SLUG = "lucide:key-round"
ICON_SLUG_PATTERN = re.compile(r"^[a-z0-9-]+:[a-z0-9][a-z0-9-]*$")
TOKEN_SPLIT_PATTERN = re.compile(r"[^a-z0-9]+")
STOP_TOKENS = {
    "key",
    "value",
    "secret",
    "token",
    "url",
    "uri",
    "id",
    "name",
    "host",
    "port",
    "unknown",
    "vendor",
    "custom",
    "default",
    "service",
}
ICON_INDEX_PATH = Path(__file__).with_name("icon_index.json")


def normalize_icon_slug(value: Optional[str]) -> str:
    if value is None:
        return ""
    return value.strip().lower()


def is_valid_icon_slug(value: str) -> bool:
    return bool(value and ICON_SLUG_PATTERN.fullmatch(value))


@lru_cache(maxsize=1)
def _load_index() -> Dict[str, Dict[str, object]]:
    try:
        with ICON_INDEX_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        terms = payload.get("terms")
        if isinstance(terms, dict):
            return terms
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}
    return {}


def _candidate_terms(tokens: Iterable[str]) -> Iterable[Tuple[str, int]]:
    normalized_tokens = [token for token in tokens if token and token not in STOP_TOKENS]
    for token in normalized_tokens:
        if len(token) >= 3:
            yield token, 1

    for size in (3, 2):
        if len(normalized_tokens) < size:
            continue
        for index in range(0, len(normalized_tokens) - size + 1):
            window = normalized_tokens[index : index + size]
            if any(len(token) < 3 for token in window):
                continue
            yield "-".join(window), size
            yield "".join(window), size


def guess_icon_slug(key: str) -> str:
    index = _load_index()
    if not index:
        return DEFAULT_ICON_SLUG

    tokens = [token for token in TOKEN_SPLIT_PATTERN.split(key.lower()) if token]
    if not tokens:
        return DEFAULT_ICON_SLUG

    best_score: Optional[Tuple[float, int, str]] = None
    best_slug = DEFAULT_ICON_SLUG
    for term, term_size in _candidate_terms(tokens):
        entry = index.get(term)
        if not isinstance(entry, dict):
            continue

        slug = entry.get("slug")
        if not isinstance(slug, str):
            continue

        count_value = entry.get("count")
        count = count_value if isinstance(count_value, int) else 0
        if len(term) <= 4 and count > 250:
            continue
        if len(term) <= 3 and count > 40:
            continue

        score = float(term_size * 10 + min(len(term), 30))
        if count > 1:
            score -= min(count / 50.0, 6.0)
        simple_icons_bonus = 1 if slug.startswith("simple-icons:") else 0
        candidate = (score, simple_icons_bonus, slug)
        if best_score is None or candidate > best_score:
            best_score = candidate
            best_slug = slug

    return best_slug


def resolve_icon_slug(key: str, icon_slug_override: Optional[str]) -> str:
    normalized_override = normalize_icon_slug(icon_slug_override)
    if is_valid_icon_slug(normalized_override):
        return normalized_override
    return guess_icon_slug(key)

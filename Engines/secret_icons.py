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


def _normalize_tokens(tokens: Iterable[str]) -> list[str]:
    return [token for token in tokens if token and token not in STOP_TOKENS]


def _first_token_terms(tokens: list[str]) -> Iterable[Tuple[str, int]]:
    if not tokens:
        return

    first = tokens[0]
    if len(first) < 3:
        return

    yielded = set()

    def emit(term: str, size: int) -> Iterable[Tuple[str, int]]:
        if term in yielded:
            return
        yielded.add(term)
        yield term, size

    yield from emit(first, 1)

    if len(tokens) >= 2 and len(tokens[1]) >= 3:
        first_two = tokens[0:2]
        yield from emit("-".join(first_two), 2)
        yield from emit("".join(first_two), 2)

    if len(tokens) >= 3 and all(len(token) >= 3 for token in tokens[0:3]):
        first_three = tokens[0:3]
        yield from emit("-".join(first_three), 3)
        yield from emit("".join(first_three), 3)


def _fallback_single_terms(tokens: list[str]) -> Iterable[Tuple[str, int]]:
    yielded = set()
    for token in tokens[1:]:
        if len(token) < 3 or token in yielded:
            continue
        yielded.add(token)
        yield token, 1


def _fallback_window_terms(tokens: list[str]) -> Iterable[Tuple[str, int]]:
    yielded = set()

    for size in (3, 2):
        if len(tokens) < size:
            continue
        for index in range(0, len(tokens) - size + 1):
            window = tokens[index : index + size]
            if index == 0:
                continue
            if any(len(token) < 3 for token in window):
                continue
            hyphen_term = "-".join(window)
            compact_term = "".join(window)
            if hyphen_term not in yielded:
                yielded.add(hyphen_term)
                yield hyphen_term, size
            if compact_term not in yielded:
                yielded.add(compact_term)
                yield compact_term, size


def _fallback_terms(tokens: list[str]) -> Iterable[Tuple[str, int]]:
    for term, size in _fallback_single_terms(tokens):
        yield term, size
    for term, size in _fallback_window_terms(tokens):
        yield term, size


def _best_slug_for_terms(
    index: Dict[str, Dict[str, object]], terms: Iterable[Tuple[str, int]]
) -> str:
    best_score: Optional[Tuple[float, int, str]] = None
    best_slug = ""
    for term, term_size in terms:
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


def guess_icon_slug(key: str) -> str:
    index = _load_index()
    if not index:
        return DEFAULT_ICON_SLUG

    tokens = _normalize_tokens(
        token for token in TOKEN_SPLIT_PATTERN.split(key.lower()) if token
    )
    if not tokens:
        return DEFAULT_ICON_SLUG

    first_slug = _best_slug_for_terms(index, _first_token_terms(tokens))
    if first_slug:
        return first_slug

    fallback_slug = _best_slug_for_terms(index, _fallback_terms(tokens))
    if fallback_slug:
        return fallback_slug

    return DEFAULT_ICON_SLUG


def resolve_icon_slug(key: str, icon_slug_override: Optional[str]) -> str:
    normalized_override = normalize_icon_slug(icon_slug_override)
    if is_valid_icon_slug(normalized_override):
        return normalized_override
    return guess_icon_slug(key)

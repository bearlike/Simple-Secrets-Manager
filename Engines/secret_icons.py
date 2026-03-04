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


class _IconSlugResolutionService:
    def __init__(self, index: Dict[str, Dict[str, object]]):
        self._index = index

    def guess(self, key: str) -> str:
        if not self._index:
            return DEFAULT_ICON_SLUG

        tokens = self._tokens_for_key(key)
        if not tokens:
            return DEFAULT_ICON_SLUG

        best_slug = self._best_slug_for_terms(self._first_pass_terms(tokens))
        if best_slug:
            return best_slug

        best_slug = self._best_slug_for_terms(self._fallback_terms(tokens))
        return best_slug or DEFAULT_ICON_SLUG

    @staticmethod
    def _tokens_for_key(key: str) -> list[str]:
        raw_tokens = TOKEN_SPLIT_PATTERN.split(key.lower())
        return [
            token for token in raw_tokens if token and token not in STOP_TOKENS
        ]

    @staticmethod
    def _push_term(
        yielded: set[str], term: str, size: int
    ) -> Iterable[Tuple[str, int]]:
        if term in yielded:
            return
        yielded.add(term)
        yield term, size

    def _first_pass_terms(
        self, tokens: list[str]
    ) -> Iterable[Tuple[str, int]]:
        if not tokens:
            return
        if len(tokens[0]) < 3:
            return

        yielded: set[str] = set()
        yield from self._push_term(yielded, tokens[0], 1)
        if self._has_min_length(tokens, 2):
            yield from self._joined_terms(yielded, tokens[0:2], 2)
        if self._has_min_length(tokens, 3):
            yield from self._joined_terms(yielded, tokens[0:3], 3)

    @staticmethod
    def _has_min_length(tokens: list[str], size: int) -> bool:
        if len(tokens) < size:
            return False
        return all(len(token) >= 3 for token in tokens[0:size])

    def _joined_terms(
        self, yielded: set[str], window: list[str], size: int
    ) -> Iterable[Tuple[str, int]]:
        yield from self._push_term(yielded, "-".join(window), size)
        yield from self._push_term(yielded, "".join(window), size)

    def _fallback_terms(self, tokens: list[str]) -> Iterable[Tuple[str, int]]:
        yield from self._fallback_single_terms(tokens)
        yield from self._fallback_window_terms(tokens)

    @staticmethod
    def _fallback_single_terms(
        tokens: list[str],
    ) -> Iterable[Tuple[str, int]]:
        yielded: set[str] = set()
        for token in tokens[1:]:
            if len(token) < 3:
                continue
            if token in yielded:
                continue
            yielded.add(token)
            yield token, 1

    def _fallback_window_terms(
        self, tokens: list[str]
    ) -> Iterable[Tuple[str, int]]:
        yielded: set[str] = set()
        for size in (3, 2):
            yield from self._window_terms(tokens, size, yielded)

    def _window_terms(
        self, tokens: list[str], size: int, yielded: set[str]
    ) -> Iterable[Tuple[str, int]]:
        if len(tokens) < size:
            return
        for index in range(1, len(tokens) - size + 1):
            window = tokens[index : index + size]
            if any(len(token) < 3 for token in window):
                continue
            yield from self._joined_terms(yielded, window, size)

    def _best_slug_for_terms(self, terms: Iterable[Tuple[str, int]]) -> str:
        best_score: Optional[Tuple[float, int, str]] = None
        for term, term_size in terms:
            candidate = self._candidate_for_term(term, term_size)
            if candidate is None:
                continue
            if best_score is None or candidate > best_score:
                best_score = candidate
        return best_score[2] if best_score else ""

    def _candidate_for_term(
        self, term: str, term_size: int
    ) -> Optional[Tuple[float, int, str]]:
        entry = self._index.get(term)
        if not isinstance(entry, dict):
            return None

        slug = entry.get("slug")
        if not isinstance(slug, str):
            return None

        count = self._count(entry.get("count"))
        if self._is_filtered_short_term(term, count):
            return None

        score = self._score(term, term_size, count)
        return (score, self._simple_icons_bonus(slug), slug)

    @staticmethod
    def _count(raw_count: object) -> int:
        return raw_count if isinstance(raw_count, int) else 0

    @staticmethod
    def _is_filtered_short_term(term: str, count: int) -> bool:
        if len(term) <= 4 and count > 250:
            return True
        if len(term) <= 3 and count > 40:
            return True
        return False

    @staticmethod
    def _score(term: str, term_size: int, count: int) -> float:
        score = float(term_size * 10 + min(len(term), 30))
        if count > 1:
            score -= min(count / 50.0, 6.0)
        return score

    @staticmethod
    def _simple_icons_bonus(slug: str) -> int:
        return 1 if slug.startswith("simple-icons:") else 0


def guess_icon_slug(key: str) -> str:
    resolver = _IconSlugResolutionService(_load_index())
    return resolver.guess(key)


def resolve_icon_slug(key: str, icon_slug_override: Optional[str]) -> str:
    normalized_override = normalize_icon_slug(icon_slug_override)
    if is_valid_icon_slug(normalized_override):
        return normalized_override
    return guess_icon_slug(key)

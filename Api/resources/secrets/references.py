#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from Engines.common import is_valid_env_key, is_valid_slug

PLACEHOLDER_PATTERN = re.compile(r"\$\{([^{}]+)\}")


class SecretReferenceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class _Context:
    project_slug: str
    config_slug: str


@dataclass(frozen=True)
class _Node:
    project_slug: str
    config_slug: str
    key: str


class SecretReferenceResolver:
    def __init__(
        self,
        *,
        project_slug: str,
        config_slug: str,
        get_project_by_slug: Callable[[str], dict | None],
        get_config_by_slug: Callable[[object, str], dict | None],
        export_config: Callable[
            [object], tuple[dict | None, object, str, int]
        ],
        require_scope: Callable[[str, object, object], object] | None = None,
        max_depth: int = 8,
        root_data: dict[str, str] | None = None,
    ):
        if max_depth < 1:
            raise SecretReferenceError("placeholder_max_depth must be >= 1")
        self._root = _Context(
            project_slug=project_slug, config_slug=config_slug
        )
        self._get_project_by_slug = get_project_by_slug
        self._get_config_by_slug = get_config_by_slug
        self._export_config = export_config
        self._require_scope = require_scope
        self._max_depth = max_depth
        self._context_cache: dict[_Context, dict[str, str]] = {}
        self._resolved_cache: dict[_Node, str] = {}
        self._validated_cache: set[_Node] = set()
        if root_data is not None:
            self._context_cache[self._root] = dict(root_data)

    def resolve_map(self, data: dict[str, str]) -> dict[str, str]:
        self._context_cache[self._root] = dict(data)
        resolved: dict[str, str] = {}
        for key, value in data.items():
            node = _Node(self._root.project_slug, self._root.config_slug, key)
            resolved[key] = self._resolve_value(
                value, current=self._root, stack=(node,), depth=0
            )
        return resolved

    def _resolve_value(
        self,
        value: str,
        *,
        current: _Context,
        stack: tuple[_Node, ...],
        depth: int,
    ) -> str:
        if "${" not in value:
            return value

        def replace(match: re.Match[str]) -> str:
            token = match.group(1).strip()
            parsed = self._parse_reference(token, current)
            if parsed is None:
                return ""
            resolved = self._resolve_key(parsed, stack=stack, depth=depth)
            return "" if resolved is None else resolved

        return PLACEHOLDER_PATTERN.sub(replace, value)

    def validate_value_references(self, *, key: str, value: str) -> list[str]:
        if "${" not in value:
            return []
        current = self._root
        source = _Node(current.project_slug, current.config_slug, key)
        errors: list[str] = []
        for match in PLACEHOLDER_PATTERN.finditer(value):
            token = match.group(1).strip()
            parsed = self._parse_reference(token, current)
            if parsed is None:
                errors.append(f"Invalid reference syntax: {match.group(0)}")
                continue
            try:
                self._ensure_node_resolvable(parsed, stack=(source,), depth=0)
            except SecretReferenceError as exc:
                errors.append(exc.message)
        return sorted(set(errors))

    def _ensure_node_resolvable(
        self, node: _Node, *, stack: tuple[_Node, ...], depth: int
    ) -> None:
        if depth >= self._max_depth:
            raise SecretReferenceError(
                f"Secret reference max depth exceeded "
                f"({self._max_depth}) while validating "
                f"{node.project_slug}.{node.config_slug}.{node.key}"
            )
        if node in stack:
            path = " -> ".join(
                f"{item.project_slug}.{item.config_slug}.{item.key}"
                for item in (*stack, node)
            )
            raise SecretReferenceError(
                f"Secret reference cycle detected: {path}"
            )
        if node in self._validated_cache:
            return

        context = _Context(node.project_slug, node.config_slug)
        data = self._load_context_data(context)
        raw_value = data.get(node.key)
        if raw_value is None:
            raise SecretReferenceError(
                "Unresolved reference: "
                f"${{{node.project_slug}.{node.config_slug}.{node.key}}}"
            )

        for match in PLACEHOLDER_PATTERN.finditer(raw_value):
            token = match.group(1).strip()
            parsed = self._parse_reference(token, context)
            if parsed is None:
                raise SecretReferenceError(
                    "Invalid reference syntax in "
                    f"{node.project_slug}.{node.config_slug}.{node.key}: "
                    f"{match.group(0)}"
                )
            self._ensure_node_resolvable(
                parsed, stack=(*stack, node), depth=depth + 1
            )

        self._validated_cache.add(node)

    def _resolve_key(
        self, node: _Node, *, stack: tuple[_Node, ...], depth: int
    ) -> str | None:
        if depth >= self._max_depth:
            raise SecretReferenceError(
                f"Secret reference max depth exceeded "
                f"({self._max_depth}) while resolving "
                f"{node.project_slug}.{node.config_slug}.{node.key}"
            )
        if node in stack:
            path = " -> ".join(
                f"{item.project_slug}.{item.config_slug}.{item.key}"
                for item in (*stack, node)
            )
            raise SecretReferenceError(
                f"Secret reference cycle detected: {path}"
            )
        if node in self._resolved_cache:
            return self._resolved_cache[node]

        context = _Context(node.project_slug, node.config_slug)
        data = self._load_context_data(context)
        raw_value = data.get(node.key)
        if raw_value is None:
            return None

        resolved = self._resolve_value(
            raw_value, current=context, stack=(*stack, node), depth=depth + 1
        )
        self._resolved_cache[node] = resolved
        return resolved

    def _parse_reference(self, token: str, current: _Context) -> _Node | None:
        parts = token.split(".")
        if len(parts) == 1:
            key = parts[0]
            if not is_valid_env_key(key):
                return None
            return _Node(current.project_slug, current.config_slug, key)
        if len(parts) == 2:
            config_slug, key = parts
            if not (is_valid_slug(config_slug) and is_valid_env_key(key)):
                return None
            return _Node(current.project_slug, config_slug, key)
        if len(parts) == 3:
            project_slug, config_slug, key = parts
            if not (
                is_valid_slug(project_slug)
                and is_valid_slug(config_slug)
                and is_valid_env_key(key)
            ):
                return None
            return _Node(project_slug, config_slug, key)
        return None

    def _load_context_data(self, context: _Context) -> dict[str, str]:
        cached = self._context_cache.get(context)
        if cached is not None:
            return cached

        project = self._get_project_by_slug(context.project_slug)
        if project is None:
            self._context_cache[context] = {}
            return self._context_cache[context]
        config = self._get_config_by_slug(project["_id"], context.config_slug)
        if config is None:
            self._context_cache[context] = {}
            return self._context_cache[context]
        if self._require_scope is not None:
            self._require_scope("secrets:read", project["_id"], config["_id"])

        data, _, msg, code = self._export_config(config["_id"])
        if code == 404 or data is None:
            self._context_cache[context] = {}
            return self._context_cache[context]
        if code >= 400:
            raise SecretReferenceError(
                msg, status_code=code if code >= 400 else 400
            )

        self._context_cache[context] = data
        return data

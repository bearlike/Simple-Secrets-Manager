from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import requests  # type: ignore[import-untyped]


@dataclass
class ApiError(Exception):
    message: str
    status_code: int = 1
    body: Any = None


def normalize_base_url(value: str) -> str:
    url = value.strip().rstrip("/")
    if not url:
        return url
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"http://{url}"

    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path.endswith("/api"):
        path = f"{path}/api" if path else "/api"
    normalized = parsed._replace(path=path, query="", fragment="").geturl()
    return normalized.rstrip("/")


class ApiClient:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        timeout: int = 10,
        retries: int = 2,
    ):
        self.base_url = normalize_base_url(base_url)
        self.token = token
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()

    def _build_url(self, path: str) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        return urljoin(f"{self.base_url}/", clean_path.lstrip("/"))

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        token: str | None = None,
        basic_auth: tuple[str, str] | None = None,
        accept: str | None = None,
    ) -> Any:
        headers: dict[str, str] = {}
        effective_token = token if token is not None else self.token
        if effective_token:
            headers["Authorization"] = f"Bearer {effective_token}"
        if accept:
            headers["Accept"] = accept

        url = self._build_url(path)
        last_exception: Exception | None = None

        for attempt in range(self.retries + 1):
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json_body,
                    headers=headers,
                    auth=basic_auth,
                    timeout=self.timeout,
                )
                return self._parse_response(response)
            except requests.RequestException as exc:
                last_exception = exc
                if attempt >= self.retries:
                    break
                time.sleep(0.2 * (attempt + 1))

        raise ApiError(
            message=f"Network error: {last_exception}", status_code=1
        )

    def _parse_response(self, response: requests.Response) -> Any:
        content_type = response.headers.get("content-type", "")

        if response.status_code >= 400:
            body = self._safe_parse(response, content_type)
            message = self._error_message(body, response.status_code)
            raise ApiError(
                message=message, status_code=response.status_code, body=body
            )

        return self._safe_parse(response, content_type)

    @staticmethod
    def _safe_parse(response: requests.Response, content_type: str) -> Any:
        if response.status_code == 204:
            return None
        if "application/json" in content_type:
            try:
                return response.json()
            except Exception:
                return {}
        return response.text

    @staticmethod
    def _error_message(body: Any, status_code: int) -> str:
        if isinstance(body, str) and body.strip():
            return body.strip()
        if isinstance(body, dict):
            for key in ("message", "error", "status"):
                value = body.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return f"API request failed ({status_code})"

    @staticmethod
    def _expect_dict(payload: Any, what: str) -> dict[str, Any]:
        """Validate a parsed response is a dict, or raise ``ApiError``.

        Shared by ~15 methods that just hand back the raw response dict;
        ``what`` supplies the per-method noun for the error message (for
        example "Profile", producing "Profile response is invalid").
        """
        if not isinstance(payload, dict):
            raise ApiError(
                f"{what} response is invalid", status_code=1, body=payload
            )
        return payload

    @staticmethod
    def _expect_list(
        payload: Any, key: str, what: str
    ) -> list[dict[str, Any]]:
        """Validate ``payload[key]`` is a list of dicts, or raise.

        Shared by the list-endpoint methods that unwrap one envelope key
        (``"projects"``, ``"members"``, ...) and filter out any non-dict
        item defensively. ``what`` supplies the per-method noun, same as
        ``_expect_dict``.
        """
        items = payload.get(key) if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise ApiError(
                f"{what} response is invalid", status_code=1, body=payload
            )
        return [item for item in items if isinstance(item, dict)]

    def login_userpass(self, username: str, password: str) -> dict[str, Any]:
        payload = self.request(
            "GET", "/auth/tokens/", basic_auth=(username, password)
        )
        if not isinstance(payload, dict) or not isinstance(
            payload.get("token"), str
        ):
            raise ApiError(
                "Token response is invalid", status_code=1, body=payload
            )
        return payload

    def export_secrets_json(
        self,
        project: str,
        config: str,
        *,
        resolve_references: bool = True,
        raw: bool = False,
    ) -> dict[str, str]:
        payload = self.request(
            "GET",
            f"/projects/{project}/configs/{config}/secrets",
            params={
                "format": "json",
                "include_parent": "true",
                "include_meta": "false",
                "raw": str(raw).lower(),
                "resolve_references": str(
                    resolve_references and not raw
                ).lower(),
            },
            accept="application/json",
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ApiError(
                "Secrets response is invalid", status_code=1, body=payload
            )

        return {
            key: value
            for key, value in data.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    def upsert_secret(
        self, project: str, config: str, key: str, value: str
    ) -> None:
        self.request(
            "PUT",
            f"/projects/{project}/configs/{config}/secrets/{key}",
            json_body={"value": value},
            accept="application/json",
        )

    def list_projects(self) -> list[dict[str, Any]]:
        payload = self.request("GET", "/projects", accept="application/json")
        return self._expect_list(payload, "projects", "Projects")

    def list_configs(self, project: str) -> list[dict[str, Any]]:
        payload = self.request(
            "GET",
            f"/projects/{project}/configs",
            accept="application/json",
        )
        return self._expect_list(payload, "configs", "Configs")

    def get_me(self) -> dict[str, Any]:
        payload = self.request("GET", "/me", accept="application/json")
        return self._expect_dict(payload, "Profile")

    def get_workspace_settings(self) -> dict[str, Any]:
        payload = self.request(
            "GET", "/workspace/settings", accept="application/json"
        )
        return self._expect_dict(payload, "Workspace settings")

    def update_workspace_settings(
        self, updates: dict[str, Any]
    ) -> dict[str, Any]:
        payload = self.request(
            "PATCH",
            "/workspace/settings",
            json_body=updates,
            accept="application/json",
        )
        return self._expect_dict(payload, "Workspace settings update")

    def list_workspace_members(self) -> list[dict[str, Any]]:
        payload = self.request(
            "GET", "/workspace/members", accept="application/json"
        )
        return self._expect_list(payload, "members", "Workspace members")

    def create_workspace_member(
        self,
        *,
        username: str,
        password: str,
        email: str | None = None,
        full_name: str | None = None,
        workspace_role: str | None = None,
    ) -> dict[str, Any]:
        payload = self.request(
            "POST",
            "/workspace/members",
            json_body={
                "username": username,
                "password": password,
                "email": email,
                "fullName": full_name,
                "workspaceRole": workspace_role,
            },
            accept="application/json",
        )
        return self._expect_dict(payload, "Workspace member create")

    def update_workspace_member(
        self, username: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        payload = self.request(
            "PATCH",
            f"/workspace/members/{username}",
            json_body=updates,
            accept="application/json",
        )
        return self._expect_dict(payload, "Workspace member update")

    def disable_workspace_member(self, username: str) -> dict[str, Any]:
        payload = self.request(
            "DELETE",
            f"/workspace/members/{username}",
            accept="application/json",
        )
        return self._expect_dict(payload, "Workspace member disable")

    def list_workspace_groups(self) -> list[dict[str, Any]]:
        payload = self.request(
            "GET", "/workspace/groups", accept="application/json"
        )
        return self._expect_list(payload, "groups", "Workspace groups")

    def create_workspace_group(
        self,
        slug: str,
        name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        payload = self.request(
            "POST",
            "/workspace/groups",
            json_body={"slug": slug, "name": name, "description": description},
            accept="application/json",
        )
        return self._expect_dict(payload, "Workspace group create")

    def update_workspace_group(
        self,
        group_slug: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        payload = self.request(
            "PATCH",
            f"/workspace/groups/{group_slug}",
            json_body={"name": name, "description": description},
            accept="application/json",
        )
        return self._expect_dict(payload, "Workspace group update")

    def delete_workspace_group(self, group_slug: str) -> dict[str, Any]:
        payload = self.request(
            "DELETE",
            f"/workspace/groups/{group_slug}",
            accept="application/json",
        )
        return self._expect_dict(payload, "Workspace group delete")

    def list_workspace_group_members(self, group_slug: str) -> list[str]:
        payload = self.request(
            "GET",
            f"/workspace/groups/{group_slug}/members",
            accept="application/json",
        )
        members = payload.get("members") if isinstance(payload, dict) else None
        if not isinstance(members, list):
            raise ApiError(
                "Workspace group members response is invalid",
                status_code=1,
                body=payload,
            )
        return [item for item in members if isinstance(item, str)]

    def update_workspace_group_members(
        self,
        group_slug: str,
        *,
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> dict[str, Any]:
        payload = self.request(
            "PUT",
            f"/workspace/groups/{group_slug}/members",
            json_body={"add": add or [], "remove": remove or []},
            accept="application/json",
        )
        return self._expect_dict(payload, "Workspace group members update")

    def list_workspace_group_mappings(self) -> list[dict[str, Any]]:
        payload = self.request(
            "GET", "/workspace/group-mappings", accept="application/json"
        )
        return self._expect_list(payload, "mappings", "Workspace mappings")

    def create_workspace_group_mapping(
        self,
        *,
        provider: str,
        external_group_key: str,
        group_slug: str,
    ) -> dict[str, Any]:
        payload = self.request(
            "POST",
            "/workspace/group-mappings",
            json_body={
                "provider": provider,
                "externalGroupKey": external_group_key,
                "groupSlug": group_slug,
            },
            accept="application/json",
        )
        return self._expect_dict(payload, "Workspace mapping create")

    def delete_workspace_group_mapping(
        self, mapping_id: str
    ) -> dict[str, Any]:
        payload = self.request(
            "DELETE",
            f"/workspace/group-mappings/{mapping_id}",
            accept="application/json",
        )
        return self._expect_dict(payload, "Workspace mapping delete")

    def list_workspace_project_members(
        self, project_slug: str
    ) -> list[dict[str, Any]]:
        payload = self.request(
            "GET",
            f"/workspace/projects/{project_slug}/members",
            accept="application/json",
        )
        return self._expect_list(payload, "members", "Project members")

    def set_workspace_project_member(
        self,
        *,
        project_slug: str,
        subject_type: str,
        subject_id: str,
        role: str,
    ) -> dict[str, Any]:
        payload = self.request(
            "PUT",
            f"/workspace/projects/{project_slug}/members",
            json_body={
                "subjectType": subject_type,
                "subjectId": subject_id,
                "role": role,
            },
            accept="application/json",
        )
        return self._expect_dict(payload, "Project member update")

    def remove_workspace_project_member(
        self,
        *,
        project_slug: str,
        subject_type: str,
        subject_id: str,
    ) -> dict[str, Any]:
        payload = self.request(
            "DELETE",
            f"/workspace/projects/{project_slug}/members/{subject_type}/{subject_id}",
            accept="application/json",
        )
        return self._expect_dict(payload, "Project member delete")

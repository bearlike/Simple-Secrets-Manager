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
    def __init__(self, base_url: str, token: str | None = None, timeout: int = 10, retries: int = 2):
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

        raise ApiError(message=f"Network error: {last_exception}", status_code=1)

    def _parse_response(self, response: requests.Response) -> Any:
        content_type = response.headers.get("content-type", "")

        if response.status_code >= 400:
            body = self._safe_parse(response, content_type)
            message = self._error_message(body, response.status_code)
            raise ApiError(message=message, status_code=response.status_code, body=body)

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

    def login_userpass(self, username: str, password: str) -> dict[str, Any]:
        payload = self.request("GET", "/auth/tokens/", basic_auth=(username, password))
        if not isinstance(payload, dict) or not isinstance(payload.get("token"), str):
            raise ApiError("Token response is invalid", status_code=1, body=payload)
        return payload

    def export_secrets_json(self, project: str, config: str) -> dict[str, str]:
        payload = self.request(
            "GET",
            f"/projects/{project}/configs/{config}/secrets",
            params={"format": "json", "include_parent": "true", "include_meta": "false"},
            accept="application/json",
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ApiError("Secrets response is invalid", status_code=1, body=payload)

        parsed: dict[str, str] = {}
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                parsed[key] = value
        return parsed

    def list_projects(self) -> list[dict[str, Any]]:
        payload = self.request("GET", "/projects", accept="application/json")
        projects = payload.get("projects") if isinstance(payload, dict) else None
        if not isinstance(projects, list):
            raise ApiError("Projects response is invalid", status_code=1, body=payload)
        return [item for item in projects if isinstance(item, dict)]

"""Thin, headless SSM HTTP client.

Mirrors ``ssm_cli/api.py`` conventions (Bearer token, ``requests``
session, small retry loop, ``{"message": ...}`` error extraction) but is
deliberately tiny: the service only needs two calls. It intentionally
does NOT import ``ssm_cli`` (that pulls ``click``/``keyring``, unwanted in
a daemon).

Path convention: unlike the CLI client, paths are joined onto
``SSM_BASE_URL`` *verbatim* to match the ssm-reload API contract
(``GET {SSM_BASE_URL}/projects/...``). Point ``SSM_BASE_URL`` at the API
root that serves those paths (e.g. ``http://ssm:5000/api``).
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin, urlparse

import requests  # type: ignore[import-untyped]

from ssm_reload.errors import SsmClientError


def normalize_base_url(value: str) -> str:
    """Trim trailing slashes and default a missing scheme to http."""
    url = value.strip().rstrip("/")
    if not url:
        return url
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    parsed = urlparse(url)
    normalized = parsed._replace(query="", fragment="").geturl()
    return normalized.rstrip("/")


class SsmClient:
    """Two-call SSM API client used by the reconcile loop."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: int = 10,
        retries: int = 2,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.token = token
        self.timeout = timeout
        self.retries = retries
        self.session = session or requests.Session()

    def _url(self, path: str) -> str:
        clean = path if path.startswith("/") else f"/{path}"
        return urljoin(f"{self.base_url}/", clean.lstrip("/"))

    def _send(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        merged: dict[str, str] = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if headers:
            merged.update(headers)

        url = self._url(path)
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json_body,
                    headers=merged,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= self.retries:
                    break
                time.sleep(0.2 * (attempt + 1))

        raise SsmClientError(f"Network error: {last_exc}", status_code=None)

    def conditional_export(
        self, project: str, config: str, etag: str | None
    ) -> tuple[bool, dict[str, str] | None, str | None]:
        """Conditionally export a config's resolved secrets.

        Returns ``(changed, secrets, new_etag)``:

        * ``304 Not Modified`` -> ``(False, None, None)``.
        * ``200 OK`` -> ``(True, {key: value}, "<etag>")`` where the ETag
          response header is stored verbatim as the new revision.

        Raises :class:`SsmClientError` on any network or HTTP error so the
        loop can skip the config and leave containers untouched.
        """
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag

        response = self._send(
            "GET",
            f"/projects/{project}/configs/{config}/secrets",
            params={
                "format": "json",
                "include_parent": "true",
                "resolve_references": "true",
            },
            headers=headers,
        )

        if response.status_code == 304:
            return (False, None, None)
        _raise_for_status(response)

        new_etag = response.headers.get("ETag")
        secrets = _parse_secret_map(response)
        return (True, secrets, new_etag)

    def report_reload(self, payload: dict[str, Any]) -> None:
        """Report a completed reload event (best-effort observability)."""
        response = self._send("POST", "/reload/events", json_body=payload)
        _raise_for_status(response)


def _raise_for_status(response: requests.Response) -> None:
    if response.status_code < 400:
        return
    raise SsmClientError(
        _error_message(response), status_code=response.status_code
    )


def _parse_secret_map(response: requests.Response) -> dict[str, str]:
    try:
        body = response.json()
    except ValueError as exc:
        raise SsmClientError(
            "Secrets response was not valid JSON", status_code=None
        ) from exc
    if not isinstance(body, dict):
        raise SsmClientError(
            "Secrets response is not a JSON object", status_code=None
        )
    return {
        key: value
        for key, value in body.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _error_message(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        for key in ("message", "error", "status"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return f"SSM request failed ({response.status_code})"

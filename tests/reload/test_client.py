from __future__ import annotations

from typing import Any

import pytest
import requests  # type: ignore[import-untyped]

from ssm_reload.client import SsmClient, normalize_base_url
from ssm_reload.errors import SsmClientError


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        headers: dict[str, str] | None = None,
        body: Any = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body

    def json(self) -> Any:
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self._responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _client(responses: list[Any]) -> tuple[SsmClient, FakeSession]:
    session = FakeSession(responses)
    client = SsmClient(
        "http://ssm:5000/api", "tok", retries=1, session=session
    )
    return client, session


def test_normalize_base_url_keeps_path_and_adds_scheme():
    assert normalize_base_url("ssm:5000/api") == "http://ssm:5000/api"
    assert normalize_base_url("http://ssm/api/") == "http://ssm/api"


def test_conditional_export_304_not_modified():
    client, session = _client([FakeResponse(304)])
    changed, secrets, etag = client.conditional_export("p", "c", '"v1"')
    assert changed is False
    assert secrets is None
    assert etag is None
    # If-None-Match sent verbatim.
    assert session.calls[0]["headers"]["If-None-Match"] == '"v1"'


def test_conditional_export_requests_value_only_representation():
    # PINNED CONTRACT: the reloader must request include_meta=false. The
    # server's include_meta DEFAULTS to true and the export ETag covers
    # everything the body carries -- omit this param and every icon/
    # description/sensitivity edit would flip the revision and recreate
    # containers.
    client, session = _client([FakeResponse(304)])
    client.conditional_export("p", "c", None)
    params = session.calls[0]["params"]
    assert params["include_meta"] == "false"
    assert params["resolve_references"] == "true"
    assert params["include_parent"] == "true"


def test_conditional_export_200_returns_secrets_and_etag():
    # The REAL wire shape: secrets live under "data", alongside "meta"
    # and "status". Parsing the envelope top-level once injected
    # {"status": "OK"} as a container's entire environment in production
    # -- this fixture must stay envelope-shaped.
    resp = FakeResponse(
        200,
        headers={"ETag": '"v2"'},
        body={
            "data": {"A": "1", "B": "2", "skip": 3},
            "meta": {"A": {"sensitive": True}},
            "status": "OK",
        },
    )
    client, _ = _client([resp])
    changed, secrets, etag = client.conditional_export("p", "c", None)
    assert changed is True
    assert secrets == {"A": "1", "B": "2"}  # non-str values dropped
    assert etag == '"v2"'


def test_conditional_export_missing_data_map_raises():
    # FAIL-SAFE: a 200 without a "data" map must raise (reconcile then
    # skips the config), never return an empty/garbage env that would be
    # injected as a container's entire environment.
    resp = FakeResponse(200, headers={"ETag": '"v2"'}, body={"status": "OK"})
    client, _ = _client([resp])
    with pytest.raises(SsmClientError):
        client.conditional_export("p", "c", None)


def test_conditional_export_403_raises_with_status():
    client, _ = _client([FakeResponse(403, body={"message": "no"})])
    with pytest.raises(SsmClientError) as exc:
        client.conditional_export("p", "c", None)
    assert exc.value.status_code == 403


def test_conditional_export_network_error_raises_without_status():
    boom = requests.ConnectionError("down")
    client, _ = _client([boom, boom])  # retries exhausted
    with pytest.raises(SsmClientError) as exc:
        client.conditional_export("p", "c", None)
    assert exc.value.status_code is None


def test_report_reload_posts_payload():
    client, session = _client([FakeResponse(202)])
    client.report_reload({"project": "p", "container": "c"})
    call = session.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/reload/events")
    assert call["json"] == {"project": "p", "container": "c"}


def test_report_reload_error_raises():
    client, _ = _client([FakeResponse(500, body={"message": "boom"})])
    with pytest.raises(SsmClientError):
        client.report_reload({"project": "p"})

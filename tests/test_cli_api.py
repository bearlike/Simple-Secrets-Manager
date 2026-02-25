import json

import requests  # type: ignore[import-untyped]

from ssm_cli.api import ApiClient, ApiError, normalize_base_url


def _response(status_code: int, payload, content_type: str = "application/json") -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.headers["content-type"] = content_type
    if isinstance(payload, (dict, list)):
        response._content = json.dumps(payload).encode("utf-8")
    elif isinstance(payload, str):
        response._content = payload.encode("utf-8")
    else:
        response._content = b""
    response.url = "http://localhost/api"
    return response


def test_normalize_base_url_appends_api_path():
    assert normalize_base_url("localhost:8080") == "http://localhost:8080/api"
    assert normalize_base_url("http://localhost:8080/") == "http://localhost:8080/api"
    assert normalize_base_url("http://localhost:8080/api") == "http://localhost:8080/api"


def test_login_userpass_parses_token(monkeypatch):
    client = ApiClient("http://localhost:8080")

    def fake_request(**kwargs):
        assert kwargs["auth"] == ("admin", "password")
        return _response(200, {"token": "abc123", "status": "OK"})

    monkeypatch.setattr(client.session, "request", fake_request)

    payload = client.login_userpass("admin", "password")
    assert payload["token"] == "abc123"


def test_export_secrets_json_parses_values(monkeypatch):
    client = ApiClient("http://localhost:8080", token="t")

    def fake_request(**kwargs):
        assert kwargs["headers"]["Authorization"] == "Bearer t"
        assert kwargs["params"]["format"] == "json"
        assert kwargs["params"]["resolve_references"] == "true"
        assert kwargs["params"]["raw"] == "false"
        return _response(200, {"data": {"API_KEY": "value", "PORT": "8080"}, "status": "OK"})

    monkeypatch.setattr(client.session, "request", fake_request)

    data = client.export_secrets_json("proj", "cfg")
    assert data == {"API_KEY": "value", "PORT": "8080"}


def test_export_secrets_json_raw_mode_disables_resolution(monkeypatch):
    client = ApiClient("http://localhost:8080", token="t")

    def fake_request(**kwargs):
        assert kwargs["params"]["resolve_references"] == "false"
        assert kwargs["params"]["raw"] == "true"
        return _response(200, {"data": {"A": "${B}"}, "status": "OK"})

    monkeypatch.setattr(client.session, "request", fake_request)

    data = client.export_secrets_json("proj", "cfg", raw=True)
    assert data == {"A": "${B}"}


def test_request_raises_api_error_on_http_failure(monkeypatch):
    client = ApiClient("http://localhost:8080", token="t")

    def fake_request(**kwargs):
        return _response(401, {"message": "Not Authorized"})

    monkeypatch.setattr(client.session, "request", fake_request)

    try:
        client.request("GET", "/projects")
        raise AssertionError("ApiError expected")
    except ApiError as exc:
        assert exc.status_code == 401
        assert "Not Authorized" in exc.message

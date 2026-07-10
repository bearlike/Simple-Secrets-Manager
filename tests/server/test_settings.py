"""ServerSettings: the API server's single validated config surface.

Hermetic: ``ssm_server.settings`` is a LEAF (imports nothing from
``ssm_server``), so it is importable here without a live Mongo. Constructed
with kwargs (via ``populate_by_name``) and ``_env_file=None`` so a developer's
local ``.env`` never leaks into an assertion.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from ssm_server.settings import ServerSettings


def _settings(**kwargs):
    kwargs.setdefault("connection_string", "mongodb://localhost:27017")
    return ServerSettings(_env_file=None, **kwargs)


def test_connection_string_is_required(monkeypatch):
    monkeypatch.delenv("CONNECTION_STRING", raising=False)
    with pytest.raises(ValidationError):
        ServerSettings(_env_file=None)


def test_defaults():
    settings = _settings()
    assert settings.bind_host == "0.0.0.0"
    assert settings.port == 5000
    assert settings.debug is False
    assert settings.cors_origins_list == []
    assert settings.otel_exporter_otlp_endpoint is None


def test_cors_origins_parsing():
    settings = _settings(cors_origins="http://a, http://b ,,  ")
    assert settings.cors_origins_list == ["http://a", "http://b"]


def test_cors_origins_empty_is_empty_list():
    # api.py turns [] into the flask-cors "*" default at the call site.
    assert _settings(cors_origins="").cors_origins_list == []


def test_port_coerces_numeric_string():
    assert _settings(port="8000").port == 8000


def test_port_rejects_non_numeric():
    with pytest.raises(ValidationError):
        _settings(port="not-a-port")


def test_port_rejects_out_of_range():
    with pytest.raises(ValidationError):
        _settings(port=0)


@pytest.mark.parametrize(
    "given,expected",
    [("true", True), ("1", True), ("false", False), ("0", False)],
)
def test_debug_parsing(given, expected):
    assert _settings(debug=given).debug is expected


def test_token_salt_is_masked():
    settings = _settings(token_salt="pepper-and-salt")
    assert isinstance(settings.token_salt, SecretStr)
    assert "pepper-and-salt" not in repr(settings)
    assert "pepper-and-salt" not in str(settings)
    assert settings.token_salt.get_secret_value() == "pepper-and-salt"


def test_token_salt_defaults_to_empty_secret():
    assert _settings().token_salt.get_secret_value() == ""


def test_is_frozen():
    settings = _settings()
    with pytest.raises(ValidationError):
        settings.port = 1234

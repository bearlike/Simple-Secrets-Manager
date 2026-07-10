"""ReloadSettings: the reloader's single validated config surface.

Constructed directly (kwargs, via ``populate_by_name``) to bypass the
environment, or through ``load()`` which reads the environment and wraps a
pydantic ``ValidationError`` into the service's own ``SsmReloadError``.
"""

from __future__ import annotations

import pytest

from ssm_reload.config import DEFAULT_POLL_INTERVAL, ReloadSettings
from ssm_reload.errors import SsmReloadError


def _clear_env(monkeypatch):
    for name in (
        "SSM_BASE_URL",
        "SSM_TOKEN",
        "SSM_RELOAD_POLL_INTERVAL",
        "SSM_RELOAD_LOG_LEVEL",
        "SSM_RELOAD_PROJECTION_CONFIGS",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_load_requires_base_url(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("SSM_TOKEN", "t")
    with pytest.raises(SsmReloadError):
        ReloadSettings.load()


def test_load_requires_token(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("SSM_BASE_URL", "http://ssm/api")
    with pytest.raises(SsmReloadError):
        ReloadSettings.load()


def test_load_defaults(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("SSM_BASE_URL", "http://ssm/api")
    monkeypatch.setenv("SSM_TOKEN", "tok")
    settings = ReloadSettings.load()
    assert settings.base_url == "http://ssm/api"
    assert settings.token.get_secret_value() == "tok"
    assert settings.poll_interval == DEFAULT_POLL_INTERVAL
    assert settings.log_level == "INFO"
    assert settings.otel_endpoint is None


def test_load_reads_overrides(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("SSM_BASE_URL", "http://ssm/api")
    monkeypatch.setenv("SSM_TOKEN", "tok")
    monkeypatch.setenv("SSM_RELOAD_POLL_INTERVAL", "5")
    settings = ReloadSettings.load()
    assert settings.poll_interval == 5.0


@pytest.mark.parametrize("value", ["0", "-3", "nonsense", ""])
def test_bad_interval_fails_fast(monkeypatch, value):
    # Behavior change: the old parser silently fell back to 30s on garbage;
    # ReloadSettings now fails fast so a typo can't run the reloader on a
    # surprise interval.
    _clear_env(monkeypatch)
    monkeypatch.setenv("SSM_BASE_URL", "http://ssm/api")
    monkeypatch.setenv("SSM_TOKEN", "tok")
    monkeypatch.setenv("SSM_RELOAD_POLL_INTERVAL", value)
    with pytest.raises(SsmReloadError):
        ReloadSettings.load()


@pytest.mark.parametrize(
    "given,expected",
    [("debug", "DEBUG"), ("Warning", "WARNING"), ("error", "ERROR")],
)
def test_log_level_is_case_insensitive(given, expected):
    settings = ReloadSettings(
        base_url="http://ssm", token="t", log_level=given
    )
    assert settings.log_level == expected


def test_bad_log_level_fails_fast(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("SSM_BASE_URL", "http://ssm/api")
    monkeypatch.setenv("SSM_TOKEN", "tok")
    monkeypatch.setenv("SSM_RELOAD_LOG_LEVEL", "chatty")
    with pytest.raises(SsmReloadError):
        ReloadSettings.load()


def test_token_repr_does_not_leak_secret():
    settings = ReloadSettings(base_url="http://ssm", token="super-secret")
    assert "super-secret" not in repr(settings)
    assert "super-secret" not in str(settings)
    assert settings.token.get_secret_value() == "super-secret"


def test_stray_whitespace_is_trimmed():
    settings = ReloadSettings(base_url="  http://ssm/api  ", token="  tok  ")
    assert settings.base_url == "http://ssm/api"
    assert settings.token.get_secret_value() == "tok"

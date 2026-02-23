from ssm_cli.api import ApiError
from ssm_cli.main import _fetch_secrets
from ssm_cli.resolve import Resolution


def _resolution() -> Resolution:
    return Resolution(
        profile="default",
        base_url="http://localhost:8080/api",
        project="project-a",
        config="dev",
        token="token",
        token_source="file",
    )


def test_fetch_secrets_uses_cache_when_offline(monkeypatch, tmp_path):
    monkeypatch.setenv("SSM_CACHE_DIR", str(tmp_path))
    # Seed with the exact hashed filename by doing one successful save flow.
    from ssm_cli.cache import save_secret_cache

    save_secret_cache("http://localhost:8080/api", "project-a", "dev", {"A": "1"})

    data, source = _fetch_secrets(_resolution(), offline=True, cache_ttl=3600)
    assert data == {"A": "1"}
    assert source == "cache"


def test_fetch_secrets_falls_back_to_cache_on_api_error(monkeypatch, tmp_path):
    monkeypatch.setenv("SSM_CACHE_DIR", str(tmp_path))

    from ssm_cli.cache import save_secret_cache

    save_secret_cache("http://localhost:8080/api", "project-a", "dev", {"CACHED": "yes"})

    def fail_export(self, project, config):
        raise ApiError("boom", status_code=503)

    monkeypatch.setattr("ssm_cli.main.ApiClient.export_secrets_json", fail_export)

    data, source = _fetch_secrets(_resolution(), offline=False, cache_ttl=3600)
    assert data == {"CACHED": "yes"}
    assert source == "cache-fallback"


def test_fetch_secrets_raises_when_offline_cache_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("SSM_CACHE_DIR", str(tmp_path))

    try:
        _fetch_secrets(_resolution(), offline=True, cache_ttl=60)
        raise AssertionError("Expected failure")
    except Exception as exc:
        assert "No cached secrets found" in str(exc)

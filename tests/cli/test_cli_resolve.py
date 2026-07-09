import json
from pathlib import Path

from ssm_cli.resolve import resolve_context


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_resolve_precedence_flags_over_env_and_files(monkeypatch, tmp_path):
    global_file = tmp_path / "global.json"
    local_file = tmp_path / "project" / ".ssm" / "config.json"

    _write_json(
        global_file,
        {
            "active_profile": "globalprof",
            "base_url": "http://global:8080/api",
            "profiles": {
                "globalprof": {
                    "base_url": "http://profile:8080/api",
                    "project": "profile-project",
                    "config": "profile-config",
                },
                "flagprof": {
                    "base_url": "http://flag-profile:8080/api",
                    "project": "flag-profile-project",
                    "config": "flag-profile-config",
                },
            },
        },
    )
    _write_json(
        local_file,
        {
            "profile": "localprof",
            "project": "local-project",
            "config": "local-config",
        },
    )

    monkeypatch.setenv("SSM_GLOBAL_CONFIG_FILE", str(global_file))
    monkeypatch.setenv("SSM_LOCAL_CONFIG_FILE", str(local_file))
    monkeypatch.setenv("SSM_BASE_URL", "http://env:8080/api")
    monkeypatch.setenv("SSM_PROJECT", "env-project")
    monkeypatch.setenv("SSM_CONFIG", "env-config")
    monkeypatch.setenv("SSM_TOKEN", "env-token")

    result = resolve_context(
        base_url="http://flag:8080/api",
        project="flag-project",
        config="flag-config",
        profile="flagprof",
    )

    assert result.profile == "flagprof"
    assert result.base_url == "http://flag:8080/api"
    assert result.project == "flag-project"
    assert result.config == "flag-config"
    assert result.token == "env-token"
    assert result.token_source == "env"


def test_resolve_uses_env_then_local_then_global(monkeypatch, tmp_path):
    global_file = tmp_path / "global.json"
    local_file = tmp_path / "project" / ".ssm" / "config.json"

    _write_json(
        global_file,
        {
            "active_profile": "dev",
            "profiles": {
                "dev": {
                    "base_url": "http://profile-host:8080/api",
                    "project": "global-project",
                    "config": "global-config",
                }
            },
        },
    )
    _write_json(
        local_file, {"project": "local-project", "config": "local-config"}
    )

    monkeypatch.setenv("SSM_GLOBAL_CONFIG_FILE", str(global_file))
    monkeypatch.setenv("SSM_LOCAL_CONFIG_FILE", str(local_file))
    monkeypatch.delenv("SSM_PROJECT", raising=False)
    monkeypatch.delenv("SSM_CONFIG", raising=False)
    monkeypatch.delenv("SSM_TOKEN", raising=False)

    result = resolve_context()

    assert result.profile == "dev"
    assert result.base_url == "http://profile-host:8080/api"
    assert result.project == "local-project"
    assert result.config == "local-config"

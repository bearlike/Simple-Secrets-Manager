"""Read-only discovery commands: `projects list`, `configs list`, and the
keys-only `secrets keys`.

These exist so a coding agent can learn what secrets a project has without a
VALUE ever reaching a log or transcript. The keys-only guarantee is pinned
directly: resolved values must never appear in `secrets keys` output.
"""

from __future__ import annotations

from click.testing import CliRunner

from ssm_cli.main import cli
from ssm_cli.resolve import Resolution


def _resolution() -> Resolution:
    return Resolution(
        profile="dev",
        base_url="http://localhost:8080/api",
        project="payments",
        config="prod",
        token="token",
        token_source="env",
    )


def test_projects_list_renders_table(monkeypatch):
    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )
    monkeypatch.setattr(
        "ssm_cli.main.ApiClient.list_projects",
        lambda _self: [
            {"slug": "payments", "name": "Payments", "archived": False},
            {"slug": "legacy", "name": "Legacy", "archived": True},
        ],
    )

    result = CliRunner().invoke(cli, ["projects", "list"])

    assert result.exit_code == 0, result.output
    assert "payments" in result.output
    assert "Legacy" in result.output


def test_configs_list_uses_resolved_project(monkeypatch):
    seen: list[str] = []

    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )

    def fake_list_configs(_self, project):
        seen.append(project)
        return [
            {"slug": "base", "name": "Base", "parentSlug": None},
            {"slug": "prod", "name": "Prod", "parentSlug": "base"},
        ]

    monkeypatch.setattr(
        "ssm_cli.main.ApiClient.list_configs", fake_list_configs
    )

    result = CliRunner().invoke(cli, ["configs", "list"])

    assert result.exit_code == 0, result.output
    assert seen == ["payments"]
    assert "prod" in result.output
    assert "base" in result.output  # parent slug rendered


def test_configs_list_requires_a_project(monkeypatch):
    resolution = Resolution(
        profile="dev",
        base_url="http://localhost:8080/api",
        project=None,
        config=None,
        token="token",
        token_source="env",
    )
    monkeypatch.setattr("ssm_cli.main.resolve_context", lambda **_: resolution)

    result = CliRunner().invoke(cli, ["configs", "list"])

    assert result.exit_code == 2
    assert "Project is not configured" in result.output


def test_secrets_keys_prints_keys_never_values(monkeypatch, tmp_path):
    monkeypatch.setenv("SSM_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )
    monkeypatch.setattr(
        "ssm_cli.main.ApiClient.export_secrets_json",
        lambda _self, project, config, **_kwargs: {
            "API_KEY": "super-secret-value",
            "DB_PASSWORD": "hunter2",
        },
    )

    result = CliRunner().invoke(cli, ["secrets", "keys"])

    assert result.exit_code == 0, result.output
    assert "API_KEY" in result.output
    assert "DB_PASSWORD" in result.output
    # The entire point of this command: no VALUE may leak into output.
    assert "super-secret-value" not in result.output
    assert "hunter2" not in result.output

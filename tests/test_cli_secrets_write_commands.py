from pathlib import Path

from click.testing import CliRunner

from ssm_cli.api import ApiError
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


def test_secrets_set_with_value_success(monkeypatch):
    calls: list[tuple[str, str, str, str]] = []

    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )

    def fake_upsert(_self, project, config, key, value):
        calls.append((project, config, key, value))

    monkeypatch.setattr("ssm_cli.main.ApiClient.upsert_secret", fake_upsert)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["secrets", "set", "--key", "API_KEY", "--value", "abc123"]
    )

    assert result.exit_code == 0, result.output
    assert calls == [("payments", "prod", "API_KEY", "abc123")]


def test_secrets_set_with_stdin_strips_single_newline(monkeypatch):
    calls: list[tuple[str, str, str, str]] = []
    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )

    def fake_upsert(_self, project, config, key, value):
        calls.append((project, config, key, value))

    monkeypatch.setattr("ssm_cli.main.ApiClient.upsert_secret", fake_upsert)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["secrets", "set", "--key", "MULTILINE", "--value-stdin"],
        input="line1\nline2\n",
    )

    assert result.exit_code == 0, result.output
    assert calls == [("payments", "prod", "MULTILINE", "line1\nline2")]


def test_secrets_set_requires_single_value_source():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "secrets",
            "set",
            "--key",
            "API_KEY",
            "--value",
            "v",
            "--value-stdin",
        ],
    )
    assert result.exit_code == 2
    assert "Provide exactly one value source" in result.output


def test_secrets_upload_env_file_success(monkeypatch, tmp_path: Path):
    calls: list[tuple[str, str, str, str]] = []
    env_file = tmp_path / "secrets.env"
    env_file.write_text(
        "# comment\nA=1\nexport B=2\nC=a=b\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )

    def fake_upsert(_self, project, config, key, value):
        calls.append((project, config, key, value))

    monkeypatch.setattr("ssm_cli.main.ApiClient.upsert_secret", fake_upsert)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["secrets", "upload", "--env-file", str(env_file)]
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        ("payments", "prod", "A", "1"),
        ("payments", "prod", "B", "2"),
        ("payments", "prod", "C", "a=b"),
    ]


def test_secrets_upload_stdin_json_success(monkeypatch):
    calls: list[tuple[str, str, str, str]] = []
    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )

    def fake_upsert(_self, project, config, key, value):
        calls.append((project, config, key, value))

    monkeypatch.setattr("ssm_cli.main.ApiClient.upsert_secret", fake_upsert)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["secrets", "upload", "--stdin", "--format", "json"],
        input='{"DB_HOST":"localhost","DB_PORT":"5432"}',
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        ("payments", "prod", "DB_HOST", "localhost"),
        ("payments", "prod", "DB_PORT", "5432"),
    ]


def test_secrets_upload_requires_exactly_one_source():
    runner = CliRunner()
    result = runner.invoke(cli, ["secrets", "upload"])
    assert result.exit_code == 2
    assert "Choose exactly one input source" in result.output


def test_secrets_upload_json_requires_string_values(tmp_path: Path):
    json_file = tmp_path / "bad.json"
    json_file.write_text('{"A":123}', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli, ["secrets", "upload", "--json-file", str(json_file)]
    )

    assert result.exit_code == 2
    assert "must be a string" in result.output


def test_secrets_upload_continues_on_failures(monkeypatch, tmp_path: Path):
    calls: list[tuple[str, str, str, str]] = []
    env_file = tmp_path / "secrets.env"
    env_file.write_text("A=1\nB=2\nC=3\n", encoding="utf-8")

    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )

    def fake_upsert(_self, project, config, key, value):
        calls.append((project, config, key, value))
        if key == "B":
            raise ApiError("Missing scope: secrets:write", status_code=403)

    monkeypatch.setattr("ssm_cli.main.ApiClient.upsert_secret", fake_upsert)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["secrets", "upload", "--env-file", str(env_file)]
    )

    assert result.exit_code == 1
    assert calls == [
        ("payments", "prod", "A", "1"),
        ("payments", "prod", "B", "2"),
        ("payments", "prod", "C", "3"),
    ]
    assert "failed=1" in result.output
    assert "B" in result.output
    assert "Missing scope: secrets:write" in result.output


def test_secrets_set_missing_config_returns_guard_error(monkeypatch):
    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )

    def fail_upsert(_self, project, config, key, value):
        raise ApiError("Config not found", status_code=404)

    monkeypatch.setattr("ssm_cli.main.ApiClient.upsert_secret", fail_upsert)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["secrets", "set", "--key", "API_KEY", "--value", "abc123"]
    )

    assert result.exit_code == 2
    assert "project/config not found" in result.output
    assert "payments/prod" in result.output


def test_secrets_upload_fails_fast_on_missing_project_or_config(
    monkeypatch, tmp_path: Path
):
    calls: list[tuple[str, str, str, str]] = []
    env_file = tmp_path / "secrets.env"
    env_file.write_text("A=1\nB=2\n", encoding="utf-8")

    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )

    def fail_upsert(_self, project, config, key, value):
        calls.append((project, config, key, value))
        raise ApiError("Project not found", status_code=404)

    monkeypatch.setattr("ssm_cli.main.ApiClient.upsert_secret", fail_upsert)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["secrets", "upload", "--env-file", str(env_file)]
    )

    assert result.exit_code == 2
    assert len(calls) == 1
    assert calls[0][2] == "A"
    assert "project/config not found" in result.output
    assert "payments/prod" in result.output
    assert "Upload complete" not in result.output

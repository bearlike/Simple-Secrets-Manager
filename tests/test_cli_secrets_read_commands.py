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


def test_secrets_download_missing_config_returns_guard_error(monkeypatch):
    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )

    def fail_export(self, project, config, **kwargs):
        raise ApiError("Config not found", status_code=404)

    monkeypatch.setattr(
        "ssm_cli.main.ApiClient.export_secrets_json", fail_export
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["secrets", "download"])

    assert result.exit_code == 2
    assert "project/config not found" in result.output
    assert "payments/prod" in result.output


def test_run_missing_config_returns_guard_error_without_running_command(
    monkeypatch,
):
    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )

    def fail_export(self, project, config, **kwargs):
        raise ApiError("Config not found", status_code=404)

    monkeypatch.setattr(
        "ssm_cli.main.ApiClient.export_secrets_json", fail_export
    )

    run_calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def fake_run_with_env(
        command: tuple[str, ...], env: dict[str, str]
    ) -> int:
        run_calls.append((command, env))
        return 0

    monkeypatch.setattr("ssm_cli.main.run_with_env", fake_run_with_env)

    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--", "echo", "hello"])

    assert result.exit_code == 2
    assert "project/config not found" in result.output
    assert "payments/prod" in result.output
    assert run_calls == []

"""End-to-end CLI error-surfacing tests.

The user-facing contract: when the API rejects a request (missing project,
missing config, auth failure) or something unexpected happens, the CLI
prints a single clean ``Error: ...`` line and exits non-zero -- never a
Python traceback.
"""

from __future__ import annotations

from click.testing import CliRunner

from ssm_cli.api import ApiError
from ssm_cli.main import cli


def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("SSM_BASE_URL", "http://localhost:8080/api")
    monkeypatch.setenv("SSM_PROJECT", "ghost")
    monkeypatch.setenv("SSM_CONFIG", "dev")
    monkeypatch.setenv("SSM_TOKEN", "test-token")
    # Isolated, empty cache so there is no offline fallback to mask the error.
    monkeypatch.setenv("SSM_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SSM_GLOBAL_CONFIG_FILE", str(tmp_path / "g.json"))
    monkeypatch.setenv("SSM_CREDENTIALS_FILE", str(tmp_path / "c.json"))


def test_run_shows_clean_message_on_project_not_found(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)

    def not_found(self, project, config, **kwargs):
        raise ApiError("Project not found", status_code=404)

    monkeypatch.setattr(
        "ssm_cli.main.ApiClient.export_secrets_json", not_found
    )

    result = CliRunner().invoke(cli, ["run", "--", "echo", "hi"])

    assert result.exit_code != 0
    assert "Project not found" in result.output
    # No leaked traceback: the command exited via click, not an exception.
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_run_survives_unexpected_exception(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)

    def boom(self, project, config, **kwargs):
        raise ValueError("malformed API payload")

    monkeypatch.setattr("ssm_cli.main.ApiClient.export_secrets_json", boom)

    result = CliRunner().invoke(cli, ["run", "--", "echo", "hi"])

    assert result.exit_code != 0
    # Degraded to a clean message instead of surfacing a raw traceback.
    assert "Error:" in result.output
    assert "malformed API payload" in result.output

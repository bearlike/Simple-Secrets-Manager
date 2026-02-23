import json

from click.testing import CliRunner

from ssm_cli.main import cli


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_configure_and_setup_write_configs(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SSM_GLOBAL_CONFIG_FILE", str(tmp_path / "global.json"))
    monkeypatch.setenv("SSM_LOCAL_CONFIG_FILE", str(tmp_path / ".ssm" / "config.json"))
    monkeypatch.setenv("SSM_CREDENTIALS_FILE", str(tmp_path / "credentials.json"))

    runner = CliRunner()

    configured = runner.invoke(cli, ["configure", "--base-url", "http://localhost:8080", "--profile", "dev"])
    assert configured.exit_code == 0, configured.output

    setup = runner.invoke(
        cli,
        ["setup", "--project", "payments", "--config", "dev", "--profile", "dev", "--local-only"],
    )
    assert setup.exit_code == 0, setup.output

    global_data = _read_json(tmp_path / "global.json")
    assert global_data["active_profile"] == "dev"
    assert global_data["profiles"]["dev"]["base_url"] == "http://localhost:8080/api"

    local_data = _read_json(tmp_path / ".ssm" / "config.json")
    assert local_data["project"] == "payments"
    assert local_data["config"] == "dev"
    assert local_data["profile"] == "dev"

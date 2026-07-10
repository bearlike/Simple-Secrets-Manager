"""``ssm secrets materialize`` — the bootstrap half of secret projection.

An ``env_file`` must EXIST before the first ``docker compose up``, or compose
refuses to start the stack. On a first deploy no container is bound to the
config yet, so the reloader has nothing to discover — this command is how an
operator (or a systemd unit) writes the file up front.
"""

from __future__ import annotations

import stat
from pathlib import Path

from click.testing import CliRunner

from ssm_cli.main import cli
from ssm_cli.resolve import Resolution


def _resolution() -> Resolution:
    return Resolution(
        profile="dev",
        base_url="http://localhost:8080/api",
        project="vpn",
        config="zurich",
        token="token",
        token_source="env",
    )


def _patch(monkeypatch, secrets: dict[str, str]) -> None:
    monkeypatch.setattr(
        "ssm_cli.main.resolve_context", lambda **_: _resolution()
    )
    monkeypatch.setattr(
        "ssm_cli.main.ApiClient.export_secrets_json",
        lambda _self, project, config, **_kwargs: dict(secrets),
    )


def test_materialize_writes_a_dotenv_file_named_for_the_config(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("SSM_CACHE_DIR", str(tmp_path / "cache"))
    _patch(monkeypatch, {"WIREGUARD_PRIVATE_KEY": "abc="})

    result = CliRunner().invoke(
        cli, ["secrets", "materialize", "--dir", str(tmp_path / "run")]
    )

    assert result.exit_code == 0, result.output
    target = tmp_path / "run" / "vpn-zurich.env"
    assert target.read_text() == 'WIREGUARD_PRIVATE_KEY="abc="\n'
    assert oct(stat.S_IMODE(target.stat().st_mode)) == "0o640"
    # The path is printed so a script can consume it; the VALUE never is.
    assert str(target) in result.output
    assert "abc=" not in result.output


def test_materialize_accepts_an_explicit_path_for_systemd(
    monkeypatch, tmp_path
):
    # systemd's EnvironmentFile= names one exact file, not a directory.
    monkeypatch.setenv("SSM_CACHE_DIR", str(tmp_path / "cache"))
    _patch(monkeypatch, {"API_KEY": "xyz"})
    target = tmp_path / "etc" / "gluetun.env"

    result = CliRunner().invoke(
        cli, ["secrets", "materialize", "--path", str(target)]
    )

    assert result.exit_code == 0, result.output
    assert target.read_text() == 'API_KEY="xyz"\n'


def test_materialize_requires_exactly_one_destination(monkeypatch, tmp_path):
    monkeypatch.setenv("SSM_CACHE_DIR", str(tmp_path / "cache"))
    _patch(monkeypatch, {"API_KEY": "xyz"})

    result = CliRunner().invoke(cli, ["secrets", "materialize"])

    assert result.exit_code == 2
    assert "--dir" in result.output


def test_materialize_renders_the_same_bytes_as_the_reloader(
    monkeypatch, tmp_path
):
    # Load-bearing: compose folds env_file CONTENTS into its config hash. If
    # the CLI and the reloader rendered the same secrets differently, every
    # `compose up` would fight the reloader and recreate the stack.
    from ssm_projection import render_dotenv

    monkeypatch.setenv("SSM_CACHE_DIR", str(tmp_path / "cache"))
    secrets = {"B": "2", "A": "with $pace"}
    _patch(monkeypatch, secrets)

    CliRunner().invoke(cli, ["secrets", "materialize", "--dir", str(tmp_path)])

    written = Path(tmp_path / "vpn-zurich.env").read_text()
    assert written == render_dotenv(secrets)

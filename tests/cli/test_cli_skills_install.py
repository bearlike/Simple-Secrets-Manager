"""`ssm-cli skills install` -- destinations, tool detection, the TTY
questionnaire, and the non-TTY guard.

Home and project roots are steered with ``$HOME`` and ``chdir`` so the test
never touches the real user config. Interactivity is toggled by patching the
``_is_interactive`` seam, because Click's test runner always presents a
non-tty stdin.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from ssm_cli.agent_skill import SKILL_MARKDOWN, SKILL_NAME
from ssm_cli.main import cli


def _skill_file(base: Path, agent_dir: str) -> Path:
    return base / agent_dir / "skills" / SKILL_NAME / "SKILL.md"


def test_target_project_installs_both_agents(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        cli, ["skills", "install", "--target", "project"]
    )

    assert result.exit_code == 0, result.output
    claude = _skill_file(tmp_path, ".claude")
    codex = _skill_file(tmp_path, ".codex")
    # Exact generated content is written for both agents.
    assert claude.read_text(encoding="utf-8") == SKILL_MARKDOWN
    assert codex.read_text(encoding="utf-8") == SKILL_MARKDOWN


def test_agent_claude_limits_scope(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        cli,
        ["skills", "install", "--target", "project", "--agent", "claude"],
    )

    assert result.exit_code == 0, result.output
    assert _skill_file(tmp_path, ".claude").exists()
    assert not _skill_file(tmp_path, ".codex").exists()


def test_user_scope_skips_undetected_tools(monkeypatch, tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)  # only claude present
    monkeypatch.setenv("HOME", str(home))

    result = CliRunner().invoke(
        cli, ["skills", "install", "--target", "user", "--agent", "all"]
    )

    assert result.exit_code == 0, result.output
    assert _skill_file(home, ".claude").exists()
    assert not _skill_file(home, ".codex").exists()
    assert "Skipped" in result.output
    assert "codex" in result.output


def test_target_all_installs_project_and_detected_user(monkeypatch, tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)

    result = CliRunner().invoke(
        cli, ["skills", "install", "--target", "all", "--agent", "claude"]
    )

    assert result.exit_code == 0, result.output
    assert _skill_file(project, ".claude").exists()  # project scope
    assert _skill_file(home, ".claude").exists()  # user scope, detected


def test_questionnaire_installs_selected_scope(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("ssm_cli.main._is_interactive", lambda: True)

    # Answer project=yes, user=no.
    result = CliRunner().invoke(
        cli, ["skills", "install", "--agent", "claude"], input="y\nn\n"
    )

    assert result.exit_code == 0, result.output
    assert _skill_file(tmp_path, ".claude").exists()


def test_non_tty_without_target_exits_2_cleanly(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # Under CliRunner stdin is not a tty, so no prompt is possible.
    result = CliRunner().invoke(cli, ["skills", "install"])

    assert result.exit_code == 2
    assert "--target" in result.output
    # Clean exit, never a raw traceback.
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_skill_content_has_frontmatter_and_permission_rule():
    assert SKILL_MARKDOWN.startswith("---\n")
    assert "name: using-ssm" in SKILL_MARKDOWN
    assert "description:" in SKILL_MARKDOWN
    # The unmissable permission rule and keys-only guidance are the product.
    assert "consent" in SKILL_MARKDOWN
    assert "secrets keys" in SKILL_MARKDOWN

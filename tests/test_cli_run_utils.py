import os
import sys

from ssm_cli.run_utils import merge_env, run_with_env


def test_merge_env_overrides_without_mutating_parent(monkeypatch):
    monkeypatch.setenv("BASE_ONLY", "1")
    parent = dict(os.environ)

    merged = merge_env({"BASE_ONLY": "2", "NEW_KEY": "x"}, base_env=parent)

    assert parent["BASE_ONLY"] == "1"
    assert "NEW_KEY" not in parent
    assert merged["BASE_ONLY"] == "2"
    assert merged["NEW_KEY"] == "x"


def test_run_with_env_injects_into_child_process():
    command = [
        sys.executable,
        "-c",
        (
            "import os,sys; "
            "sys.exit(0 if os.getenv('SSM_TEST_KEY') == 'injected' else 7)"
        ),
    ]
    code = run_with_env(command, {"SSM_TEST_KEY": "injected"})
    assert code == 0

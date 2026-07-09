from __future__ import annotations

import pytest

from ssm_reload.config import DEFAULT_POLL_INTERVAL, Config
from ssm_reload.errors import SsmReloadError


def test_from_env_requires_base_url():
    with pytest.raises(SsmReloadError):
        Config.from_env({"SSM_TOKEN": "t"})


def test_from_env_requires_token():
    with pytest.raises(SsmReloadError):
        Config.from_env({"SSM_BASE_URL": "http://ssm/api"})


def test_from_env_defaults():
    cfg = Config.from_env(
        {"SSM_BASE_URL": "http://ssm/api", "SSM_TOKEN": "tok"}
    )
    assert cfg.base_url == "http://ssm/api"
    assert cfg.token == "tok"
    assert cfg.poll_interval == DEFAULT_POLL_INTERVAL
    assert cfg.label_prefix == "ssm"
    assert cfg.docker_host is None


def test_from_env_overrides():
    cfg = Config.from_env(
        {
            "SSM_BASE_URL": "http://ssm/api",
            "SSM_TOKEN": "tok",
            "SSM_RELOAD_POLL_INTERVAL": "5",
            "SSM_RELOAD_LABEL_PREFIX": "acme",
            "DOCKER_HOST": "tcp://d:2375",
        }
    )
    assert cfg.poll_interval == 5.0
    assert cfg.label_prefix == "acme"
    assert cfg.docker_host == "tcp://d:2375"


@pytest.mark.parametrize("value", ["0", "-3", "nonsense", ""])
def test_bad_interval_falls_back_to_default(value):
    cfg = Config.from_env(
        {
            "SSM_BASE_URL": "http://ssm/api",
            "SSM_TOKEN": "tok",
            "SSM_RELOAD_POLL_INTERVAL": value,
        }
    )
    assert cfg.poll_interval == DEFAULT_POLL_INTERVAL

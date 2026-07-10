"""Hermetic tests for the config-delete reference-integrity scan.

``find_configs_referencing`` finds configs whose stored values point at the
config about to be deleted so the delete path can 409 instead of leaving a
${...} reference that only explodes at read time.
"""

from ssm_server.engines.secrets_v2 import SecretsV2

from tests.server.fakes import FakeSecrets


def _engine(docs):
    return SecretsV2(FakeSecrets(docs), configs_engine=None)


def test_same_project_reference_blocks_delete():
    docs = [
        {"config_id": "shared", "key": "DB", "value_enc": "postgres://x"},
        {"config_id": "web", "key": "URL", "value_enc": "${shared.DB}"},
    ]
    engine = _engine(docs)
    refs = engine.find_configs_referencing(
        "shared", "alpha", "shared", ["shared", "web"]
    )
    assert refs == {"web"}


def test_cross_project_reference_blocks_delete():
    docs = [
        {
            "config_id": "beta-cfg",
            "key": "URL",
            "value_enc": "${alpha.shared.DB}",
        },
    ]
    engine = _engine(docs)
    refs = engine.find_configs_referencing(
        "shared", "alpha", "shared", ["shared"]
    )
    assert refs == {"beta-cfg"}


def test_two_part_reference_from_other_project_is_ignored():
    # A bare ${shared.DB} resolves against the referencing secret's OWN
    # project, so a config outside alpha does not depend on alpha/shared.
    docs = [
        {"config_id": "beta-cfg", "key": "URL", "value_enc": "${shared.DB}"},
    ]
    engine = _engine(docs)
    refs = engine.find_configs_referencing(
        "shared", "alpha", "shared", ["shared"]
    )
    assert refs == set()


def test_unreferenced_config_deletes_clean():
    docs = [
        {"config_id": "web", "key": "URL", "value_enc": "plain-value"},
        {"config_id": "web", "key": "OTHER", "value_enc": "${web.URL}"},
    ]
    engine = _engine(docs)
    refs = engine.find_configs_referencing(
        "shared", "alpha", "shared", ["shared", "web"]
    )
    assert refs == set()


def test_configs_own_secrets_are_ignored():
    docs = [
        {"config_id": "shared", "key": "SELF", "value_enc": "${shared.DB}"},
    ]
    engine = _engine(docs)
    refs = engine.find_configs_referencing(
        "shared", "alpha", "shared", ["shared"]
    )
    assert refs == set()

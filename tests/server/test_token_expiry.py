from datetime import datetime, timedelta, timezone

from ssm_server.access.tokens import Tokens

from tests.server.fakes import FakeCollection


def _token_doc(token_hash, expires_at):
    # expires_at is timezone-AWARE, matching what Mongo returns under the
    # tz_aware=True client. authenticate() compares it against an aware
    # datetime.now(timezone.utc); a naive value here would (correctly) raise
    # TypeError, which is exactly the read-back trap tz_aware=True avoids.
    return {
        "_id": "1",
        "token_hash": token_hash,
        "type": "service",
        "expires_at": expires_at,
        "revoked_at": None,
        "scopes": [],
    }


def test_expired_token_is_rejected():
    token = "abc"
    temp = Tokens(FakeCollection([]))
    hashed = temp._hash_token(token)
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    tokens = Tokens(FakeCollection([_token_doc(hashed, expired)]))
    actor, err = tokens.authenticate(token)
    assert actor is None
    assert err == "expired"


def test_unexpired_aware_token_authenticates():
    token = "abc"
    temp = Tokens(FakeCollection([]))
    hashed = temp._hash_token(token)
    valid = datetime.now(timezone.utc) + timedelta(hours=1)
    tokens = Tokens(FakeCollection([_token_doc(hashed, valid)]))
    actor, err = tokens.authenticate(token)
    assert err is None
    assert actor is not None

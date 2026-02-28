from __future__ import annotations

from typing import Any, Optional, Tuple

from ssm_cli.config import load_credentials, save_credentials

keyring: Any
try:
    import keyring as _keyring  # type: ignore[import-untyped]

    keyring = _keyring
except Exception:  # pragma: no cover - import failure depends on platform
    keyring = None

KEYRING_SERVICE = "simple-secrets-manager-cli"
KEYRING_SENTINEL = "__KEYRING__"


def _token_key(profile: str, base_url: str) -> str:
    return f"{profile}@{base_url}"


def set_token(profile: str, base_url: str, token: str) -> str:
    key = _token_key(profile, base_url)
    creds = load_credentials()

    if keyring is not None:
        try:
            keyring.set_password(KEYRING_SERVICE, key, token)
            creds[key] = KEYRING_SENTINEL
            save_credentials(creds)
            return "keyring"
        except Exception:
            pass

    creds[key] = token
    save_credentials(creds)
    return "file"


def get_token(
    profile: str, base_url: str
) -> Tuple[Optional[str], Optional[str]]:
    key = _token_key(profile, base_url)

    if keyring is not None:
        try:
            token = keyring.get_password(KEYRING_SERVICE, key)
            if token:
                return token, "keyring"
        except Exception:
            pass

    creds = load_credentials()
    token = creds.get(key)
    if token and token != KEYRING_SENTINEL:
        return token, "file"
    return None, None


def clear_token(profile: str, base_url: str) -> None:
    key = _token_key(profile, base_url)

    if keyring is not None:
        try:
            keyring.delete_password(KEYRING_SERVICE, key)
        except Exception:
            pass

    creds = load_credentials()
    if key in creds:
        del creds[key]
        save_credentials(creds)


def clear_all_tokens() -> None:
    creds = load_credentials()
    keys = list(creds.keys())

    if keyring is not None:
        for key in keys:
            try:
                keyring.delete_password(KEYRING_SERVICE, key)
            except Exception:
                pass

    if creds:
        save_credentials({})

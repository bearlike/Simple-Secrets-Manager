from Engines.secret_icons import (
    DEFAULT_ICON_SLUG,
    guess_icon_slug,
    is_valid_icon_slug,
    resolve_icon_slug,
)


def test_guess_icon_slug_prefers_simple_icons_sqlalchemy():
    assert (
        guess_icon_slug("SQLALCHEMY_DATABASE_URI") == "simple-icons:sqlalchemy"
    )


def test_guess_icon_slug_falls_back_to_default_for_unknown_term():
    assert guess_icon_slug("XQZV_A9PZZ_SECRET") == DEFAULT_ICON_SLUG


def test_resolve_icon_slug_prefers_valid_override():
    assert (
        resolve_icon_slug("SQLALCHEMY_DATABASE_URI", "simple-icons:postgresql")
        == "simple-icons:postgresql"
    )


def test_is_valid_icon_slug_rejects_invalid_values():
    assert is_valid_icon_slug("simple-icons:sqlalchemy")
    assert not is_valid_icon_slug("simple-icons/sqlalchemy")
    assert not is_valid_icon_slug("SQLALCHEMY")

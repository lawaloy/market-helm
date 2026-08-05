"""Register/login emails must reject junk shapes, control chars, and oversize."""

import pytest

from src.storage.database import init_database
from src.storage.users import (
    MAX_EMAIL_LENGTH,
    UserError,
    authenticate_user,
    create_user,
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "email-validation.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


@pytest.mark.parametrize(
    "email",
    [
        "@",
        "a@",
        "@example.com",
        "a@@example.com",
        "no-at-sign",
        "a@b.com\ncc:evil@x.com",
        "a@b.com\r\nBcc:evil@x.com",
        "a@b.com\0hidden",
        "spaces in@example.com",
        "a@exam ple.com",
        "",
        "   ",
    ],
)
def test_create_user_rejects_invalid_email_shapes(db, email):
    with pytest.raises(UserError, match="valid email|at most"):
        create_user(email, "password123")


def test_create_user_rejects_oversized_email(db):
    huge = "a" * (MAX_EMAIL_LENGTH + 1)
    with pytest.raises(UserError, match="at most"):
        create_user(huge, "password123")


def test_create_user_accepts_email_at_max_length(db):
    domain = "@example.com"
    local = "a" * (MAX_EMAIL_LENGTH - len(domain))
    email = local + domain
    assert len(email) == MAX_EMAIL_LENGTH
    user = create_user(email, "password123")
    assert user["email"] == email


def test_create_user_still_normalizes_case_and_edges(db):
    user = create_user("  Mixed.Case@Example.COM ", "password123")
    assert user["email"] == "mixed.case@example.com"


def test_authenticate_soft_fails_on_invalid_email(db):
    create_user("ok@example.com", "password123")
    assert authenticate_user("a@b.com\ncc:x", "password123") is None
    assert authenticate_user("a" * (MAX_EMAIL_LENGTH + 1), "password123") is None
    assert authenticate_user("@", "password123") is None


def test_authenticate_accepts_normalized_valid_email(db):
    create_user("login@example.com", "password123")
    authed = authenticate_user("  LOGIN@Example.com ", "password123")
    assert authed is not None
    assert authed["email"] == "login@example.com"

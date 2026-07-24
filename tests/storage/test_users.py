"""Unit tests for user account storage."""

import pytest

from src.storage.database import init_database
from src.storage.users import UserError, authenticate_user, create_user, get_user_by_id


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


class TestUsers:
    def test_create_and_authenticate(self, db):
        user = create_user("alice@example.com", "password123")
        assert user["email"] == "alice@example.com"
        assert user["id"]

        authed = authenticate_user("alice@example.com", "password123")
        assert authed is not None
        assert authed["id"] == user["id"]

    def test_authenticate_wrong_password(self, db):
        create_user("bob@example.com", "password123")
        assert authenticate_user("bob@example.com", "wrongpass") is None

    def test_authenticate_normalizes_email_case_and_whitespace(self, db):
        user = create_user("  Alice@Example.com ", "password123")
        assert user["email"] == "alice@example.com"
        authed = authenticate_user("ALICE@example.com", "password123")
        assert authed is not None
        assert authed["id"] == user["id"]

    def test_authenticate_corrupt_password_hash_returns_none(self, db):
        user = create_user("corrupt@example.com", "password123")
        from src.storage.database import get_connection

        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                ("not-a-valid-hash", user["id"]),
            )

        assert authenticate_user("corrupt@example.com", "password123") is None

    def test_short_password_rejected(self, db):
        with pytest.raises(UserError, match="8 characters"):
            create_user("short@example.com", "short")

    def test_invalid_email_rejected(self, db):
        with pytest.raises(UserError, match="valid email"):
            create_user("not-an-email", "password123")

    def test_duplicate_email_rejected(self, db):
        create_user("dup@example.com", "password123")
        with pytest.raises(UserError, match="already exists"):
            create_user("dup@example.com", "otherpass99")

    def test_get_user_by_id(self, db):
        user = create_user("carol@example.com", "password123")
        loaded = get_user_by_id(user["id"])
        assert loaded["email"] == "carol@example.com"
        assert get_user_by_id("missing-id") is None

"""Missing-user mutations must fail closed without leaking account existence."""

import pytest

from src.storage.database import init_database
from src.storage.users import UserError, change_password, delete_user_account, revoke_user_sessions


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "missing-account.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def test_revoke_user_sessions_raises_when_user_missing(db):
    with pytest.raises(UserError, match="User not found"):
        revoke_user_sessions("missing-id")


def test_change_password_treats_missing_user_as_wrong_password(db):
    with pytest.raises(UserError, match="Current password is incorrect"):
        change_password("missing-id", "password123", "new-password-123")


def test_delete_user_account_treats_missing_user_as_wrong_password(db):
    with pytest.raises(UserError, match="Current password is incorrect"):
        delete_user_account("missing-id", "password123")

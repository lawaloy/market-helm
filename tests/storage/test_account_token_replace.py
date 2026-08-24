"""Re-issuing an account token must invalidate the previous unused token."""

import pytest

from src.storage.account_tokens import (
    RESET_PASSWORD,
    VERIFY_EMAIL,
    consume_token,
    issue_token,
)
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "account-tokens-replace.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{path.as_posix()}")
    init_database()
    return create_user("replace@example.com", "password123")


def test_issue_token_replaces_previous_unused_token(db):
    first = issue_token(db["id"], RESET_PASSWORD)
    second = issue_token(db["id"], RESET_PASSWORD)
    assert consume_token(first, RESET_PASSWORD) is None
    assert consume_token(second, RESET_PASSWORD) == db["id"]


def test_issue_token_does_not_revoke_other_purposes(db):
    verify = issue_token(db["id"], VERIFY_EMAIL)
    reset = issue_token(db["id"], RESET_PASSWORD)
    assert consume_token(verify, VERIFY_EMAIL) == db["id"]
    assert consume_token(reset, RESET_PASSWORD) == db["id"]

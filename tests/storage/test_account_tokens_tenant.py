"""issue_token and revoke_tokens must stay per-tenant.

Re-issuing a reset or verify token DELETEs unused rows for that purpose.
A missing user_id filter would invalidate every other tenant's live reset
or verify link when one user requests a new one. Existing replace tests
only cover same-user previous-token and other-purpose rows.
"""

from __future__ import annotations

import pytest

from src.storage.account_tokens import (
    RESET_PASSWORD,
    VERIFY_EMAIL,
    consume_token,
    issue_token,
    revoke_tokens,
)
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "account-tokens-tenant.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def test_issue_token_does_not_revoke_sibling_tenant_tokens(db) -> None:
    """Replacing user A's reset token must leave user B's reset and verify live."""
    user_a = create_user("token-tenant-a@example.com", "password123")["id"]
    user_b = create_user("token-tenant-b@example.com", "password123")["id"]

    reset_a = issue_token(user_a, RESET_PASSWORD)
    reset_b = issue_token(user_b, RESET_PASSWORD)
    verify_b = issue_token(user_b, VERIFY_EMAIL)

    replacement = issue_token(user_a, RESET_PASSWORD)

    assert consume_token(reset_a, RESET_PASSWORD) is None
    assert consume_token(replacement, RESET_PASSWORD) == user_a
    assert consume_token(reset_b, RESET_PASSWORD) == user_b
    assert consume_token(verify_b, VERIFY_EMAIL) == user_b


def test_revoke_tokens_does_not_delete_sibling_tenant_tokens(db) -> None:
    """revoke_tokens for one tenant must not consume another tenant's live links."""
    user_a = create_user("token-revoke-a@example.com", "password123")["id"]
    user_b = create_user("token-revoke-b@example.com", "password123")["id"]

    reset_a = issue_token(user_a, RESET_PASSWORD)
    reset_b = issue_token(user_b, RESET_PASSWORD)
    verify_b = issue_token(user_b, VERIFY_EMAIL)

    revoke_tokens(user_a, RESET_PASSWORD)

    assert consume_token(reset_a, RESET_PASSWORD) is None
    assert consume_token(reset_b, RESET_PASSWORD) == user_b
    assert consume_token(verify_b, VERIFY_EMAIL) == user_b

"""revoke_user_sessions and change_password must stay per-tenant.

Logout and password change bump session_version so existing JWTs fail.
A missing user_id filter would log every other tenant out (and, for
change_password, rewrite their password hash) when one user logs out
or rotates credentials. Existing revocation tests are single-tenant.
"""

from __future__ import annotations

import pytest

from src.storage.database import init_database
from src.storage.users import (
    authenticate_user,
    change_password,
    create_user,
    get_user_by_id,
    revoke_user_sessions,
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "session-revoke-tenant.db"
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL",
        f"sqlite:///{db_path.as_posix()}",
    )
    init_database()
    return db_path


def test_revoke_user_sessions_does_not_bump_sibling_tenant(db) -> None:
    """Logout of A must not invalidate B's still-current session_version."""
    user_a = create_user("session-revoke-a@example.com", "password123")
    user_b = create_user("session-revoke-b@example.com", "password456")
    assert user_a["session_version"] == 1
    assert user_b["session_version"] == 1

    revoke_user_sessions(user_a["id"])
    revoke_user_sessions(user_a["id"])

    loaded_a = get_user_by_id(user_a["id"])
    loaded_b = get_user_by_id(user_b["id"])
    assert loaded_a is not None and loaded_b is not None
    assert loaded_a["session_version"] == 3
    assert loaded_b["session_version"] == 1
    authed_a = authenticate_user("session-revoke-a@example.com", "password123")
    authed_b = authenticate_user("session-revoke-b@example.com", "password456")
    assert authed_a is not None and authed_b is not None
    assert authed_a["session_version"] == 3
    assert authed_b["session_version"] == 1


def test_change_password_does_not_revoke_sibling_tenant(db) -> None:
    """Password rotate for A must not rehash B or bump B's session_version."""
    user_a = create_user("session-pw-a@example.com", "password123")
    user_b = create_user("session-pw-b@example.com", "password456")

    change_password(user_a["id"], "password123", "new-password-123")

    loaded_a = get_user_by_id(user_a["id"])
    loaded_b = get_user_by_id(user_b["id"])
    assert loaded_a is not None and loaded_b is not None
    assert loaded_a["session_version"] == 2
    assert loaded_b["session_version"] == 1
    assert authenticate_user("session-pw-a@example.com", "password123") is None
    authed_a = authenticate_user("session-pw-a@example.com", "new-password-123")
    authed_b = authenticate_user("session-pw-b@example.com", "password456")
    assert authed_a is not None and authed_b is not None
    assert authed_a["id"] == user_a["id"]
    assert authed_a["session_version"] == 2
    assert authed_b["id"] == user_b["id"]
    assert authed_b["session_version"] == 1
    assert authenticate_user("session-pw-b@example.com", "new-password-123") is None

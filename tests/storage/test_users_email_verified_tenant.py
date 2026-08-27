"""mark_email_verified must stay per-tenant.

Confirming one tenant's email UPDATEs email_verified_at. Tenants share
one users table. Existing verify tests are single-tenant, so a missing
id filter would mark every other unverified account (and rewrite an
already-verified sibling's audit time) when one user confirms.
"""

from __future__ import annotations

import pytest

from src.storage.database import get_connection, init_database
from src.storage.users import (
    create_user,
    get_user_by_id,
    mark_email_verified,
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "email-verified-tenant.db"
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL",
        f"sqlite:///{db_path.as_posix()}",
    )
    init_database()
    return db_path


def _verified_at(user_id: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT email_verified_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return row["email_verified_at"]


def test_mark_email_verified_does_not_verify_sibling_tenant(db) -> None:
    """Confirming A must not mark unverified B as verified."""
    user_a = create_user("verify-tenant-a@example.com", "password123")
    user_b = create_user("verify-tenant-b@example.com", "password456")
    assert get_user_by_id(user_a["id"])["email_verified"] is False
    assert get_user_by_id(user_b["id"])["email_verified"] is False
    assert user_a["session_version"] == 1
    assert user_b["session_version"] == 1

    mark_email_verified(user_a["id"])

    loaded_a = get_user_by_id(user_a["id"])
    loaded_b = get_user_by_id(user_b["id"])
    assert loaded_a is not None and loaded_b is not None
    assert loaded_a["email_verified"] is True
    assert loaded_b["email_verified"] is False
    assert _verified_at(user_a["id"])
    assert _verified_at(user_b["id"]) is None
    assert loaded_a["session_version"] == 1
    assert loaded_b["session_version"] == 1


def test_mark_email_verified_does_not_rewrite_sibling_timestamp(db) -> None:
    """Confirming A must not rewrite already-verified B's audit time."""
    user_a = create_user("verify-stamp-a@example.com", "password123")
    user_b = create_user("verify-stamp-b@example.com", "password456")

    mark_email_verified(user_b["id"])
    stamp_b = _verified_at(user_b["id"])
    assert stamp_b
    assert get_user_by_id(user_b["id"])["email_verified"] is True

    mark_email_verified(user_a["id"])
    mark_email_verified(user_a["id"])

    loaded_a = get_user_by_id(user_a["id"])
    loaded_b = get_user_by_id(user_b["id"])
    assert loaded_a is not None and loaded_b is not None
    assert loaded_a["email_verified"] is True
    assert loaded_b["email_verified"] is True
    assert _verified_at(user_a["id"])
    assert _verified_at(user_b["id"]) == stamp_b
    assert loaded_a["session_version"] == 1
    assert loaded_b["session_version"] == 1

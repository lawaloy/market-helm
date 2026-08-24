"""Unit tests for dashboard auth helpers (mode switch + Bearer parsing)."""

import asyncio

import pytest
from fastapi import HTTPException

from dashboard.backend.auth import bearer_user_id, optional_user_id, require_user_id
from src.storage.session import create_access_token


@pytest.fixture
def auth_secret(monkeypatch):
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "test-secret-min-16-chars")


@pytest.fixture
def db_on(tmp_path, monkeypatch, auth_secret):
    db_path = tmp_path / "auth-helpers.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    from src.storage.database import init_database

    init_database()


def test_require_user_id_returns_none_when_database_disabled(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    assert asyncio.run(require_user_id(authorization=None)) is None
    assert asyncio.run(optional_user_id(authorization="Bearer anything")) is None


def test_bearer_user_id_rejects_empty_and_non_bearer(auth_secret) -> None:
    assert bearer_user_id(None) is None
    assert bearer_user_id("") is None
    assert bearer_user_id("Token abc") is None
    assert bearer_user_id("Bearer ") is None
    assert bearer_user_id("bearer   ") is None


def test_require_user_id_401_when_db_on_and_auth_missing(db_on) -> None:
    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_user_id(authorization=None))
    assert exc.value.status_code == 401
    assert "Authentication required" in exc.value.detail

    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_user_id(authorization="Bearer "))
    assert exc.value.status_code == 401


def test_require_user_id_accepts_valid_bearer_case_insensitive(db_on) -> None:
    from src.storage.users import create_user

    user = create_user("case@example.com", "password123")
    token = create_access_token(user["id"])
    assert asyncio.run(require_user_id(authorization=f"Bearer {token}")) == user["id"]
    assert asyncio.run(require_user_id(authorization=f"BEARER {token}")) == user["id"]
    assert asyncio.run(optional_user_id(authorization=f"bearer {token}")) == user["id"]


def test_require_user_id_401_when_user_deleted(db_on) -> None:
    from src.storage.database import get_connection
    from src.storage.users import create_user

    user = create_user("deleted-helper@example.com", "password123")
    token = create_access_token(user["id"])
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_user_id(authorization=f"Bearer {token}"))
    assert exc.value.status_code == 401
    assert exc.value.detail == "User not found."

    assert asyncio.run(optional_user_id(authorization=f"Bearer {token}")) is None


def test_require_user_id_401_when_session_revoked(db_on) -> None:
    from src.storage.users import create_user, revoke_user_sessions

    user = create_user("revoked-helper@example.com", "password123")
    token = create_access_token(user["id"], session_version=user["session_version"])
    revoke_user_sessions(user["id"])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_user_id(authorization=f"Bearer {token}"))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Session revoked."

    assert asyncio.run(optional_user_id(authorization=f"Bearer {token}")) is None

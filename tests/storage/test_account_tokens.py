"""Single-use account tokens must fail closed on shape, expiry, and races."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from src.storage.account_tokens import (
    RESET_PASSWORD,
    VERIFY_EMAIL,
    _digest,
    consume_token,
    issue_token,
)
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "account-tokens.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{path.as_posix()}")
    init_database()
    return create_user("tokens@example.com", "password123")


def test_issue_token_rejects_unknown_purpose(db):
    with pytest.raises(ValueError, match="Unsupported account token purpose"):
        issue_token(db["id"], "not-a-purpose")


@pytest.mark.parametrize(
    "token",
    ["", "x" * 257, None],
)
def test_consume_token_rejects_empty_oversized_and_non_string(db, token):
    assert consume_token(token, RESET_PASSWORD) is None


def test_consume_token_rejects_wrong_purpose_without_consuming(db):
    token = issue_token(db["id"], RESET_PASSWORD)
    assert consume_token(token, VERIFY_EMAIL) is None
    assert consume_token(token, RESET_PASSWORD) == db["id"]


def test_expired_token_cannot_be_consumed(db):
    token = issue_token(db["id"], RESET_PASSWORD)
    with get_connection() as conn:
        conn.execute(
            "UPDATE account_tokens SET expires_at = ? WHERE token_hash = ?",
            ("2000-01-01T00:00:00+00:00", _digest(token)),
        )
    assert consume_token(token, RESET_PASSWORD) is None


def _stored_expiry() -> datetime:
    with get_connection() as conn:
        return datetime.fromisoformat(
            conn.execute("SELECT expires_at FROM account_tokens").fetchone()["expires_at"]
        )


def test_issue_token_clamps_ttl(db):
    before = datetime.now(timezone.utc)
    issue_token(db["id"], RESET_PASSWORD, ttl_minutes=0)
    expires = _stored_expiry()
    # ttl_minutes=0 must not mint an already-expired token.
    assert timedelta(seconds=50) <= (expires - before) <= timedelta(minutes=1, seconds=10)

    before = datetime.now(timezone.utc)
    issue_token(db["id"], RESET_PASSWORD, ttl_minutes=100_000)
    expires = _stored_expiry()
    # Upper clamp is 1440 minutes so a huge TTL cannot mint a multi-week reset link.
    assert timedelta(hours=23, minutes=50) <= (expires - before) <= timedelta(days=1, seconds=10)


def test_concurrent_consume_is_single_use(db):
    token = issue_token(db["id"], RESET_PASSWORD)
    barrier = threading.Barrier(2)
    results: list[str | None] = []
    lock = threading.Lock()

    def worker() -> None:
        barrier.wait(timeout=5)
        got = consume_token(token, RESET_PASSWORD)
        with lock:
            results.append(got)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker), pool.submit(worker)]
        for future in futures:
            future.result(timeout=10)

    assert results.count(db["id"]) == 1
    assert results.count(None) == 1

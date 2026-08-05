"""Oversized passwords must fail closed before scrypt (CPU DoS guard)."""

import time

import pytest

from src.storage.database import init_database
from src.storage.users import (
    MAX_PASSWORD_LENGTH,
    UserError,
    _hash_password,
    _verify_password,
    authenticate_user,
    create_user,
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "password-length.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def test_hash_rejects_oversized_password() -> None:
    with pytest.raises(UserError, match="at most"):
        _hash_password("x" * (MAX_PASSWORD_LENGTH + 1))


def test_create_user_rejects_oversized_password(db) -> None:
    with pytest.raises(UserError, match="at most"):
        create_user("longpass@example.com", "x" * (MAX_PASSWORD_LENGTH + 1))


def test_verify_rejects_oversized_password_without_scrypt() -> None:
    stored = _hash_password("password123")
    huge = "x" * (MAX_PASSWORD_LENGTH + 1)

    started = time.perf_counter()
    assert _verify_password(huge, stored) is False
    elapsed = time.perf_counter() - started
    # Bound is generous for slow CI; real scrypt on multi-KB input is slower.
    assert elapsed < 0.5


def test_hash_accepts_password_at_max_length() -> None:
    stored = _hash_password("a" * MAX_PASSWORD_LENGTH)
    assert _verify_password("a" * MAX_PASSWORD_LENGTH, stored) is True


def test_authenticate_rejects_oversized_password(db) -> None:
    create_user("auth-long@example.com", "password123")
    assert (
        authenticate_user("auth-long@example.com", "x" * (MAX_PASSWORD_LENGTH + 1))
        is None
    )

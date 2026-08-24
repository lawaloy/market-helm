"""mark_email_verified must be idempotent so double-confirm cannot rewrite audit time."""

from src.storage.database import get_connection, init_database
from src.storage.users import create_user, get_user_by_id, mark_email_verified


def test_second_mark_email_verified_keeps_original_timestamp(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "email-verified.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    user = create_user("verify-once@example.com", "password123")
    assert get_user_by_id(user["id"])["email_verified"] is False

    mark_email_verified(user["id"])
    with get_connection() as conn:
        first = conn.execute(
            "SELECT email_verified_at FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()["email_verified_at"]
    assert first
    assert get_user_by_id(user["id"])["email_verified"] is True

    mark_email_verified(user["id"])
    with get_connection() as conn:
        second = conn.execute(
            "SELECT email_verified_at FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()["email_verified_at"]

    assert second == first

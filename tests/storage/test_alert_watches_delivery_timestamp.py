"""record_delivery must store only parseable timestamps for status/prune ordering."""

from datetime import datetime, timezone

import pytest

from src.storage.alert_watches import latest_deliveries_for_user, record_delivery
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "delivery-ts.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    user = create_user("delivery-ts@example.com", "password123")
    return user["id"]


@pytest.mark.parametrize(
    "bad_ts",
    [None, "", "   ", "not-a-timestamp", "zzzz", "2026-13-99T99:99:99Z"],
)
def test_record_delivery_falls_back_to_utc_now_for_unusable_timestamps(db_user, bad_ts) -> None:
    before = datetime.now(timezone.utc)
    record_delivery(
        db_user,
        "aapl-drop",
        "email",
        success=True,
        timestamp=bad_ts,
    )
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT timestamp FROM alert_delivery_log
            WHERE user_id = ? AND channel = ?
            ORDER BY id DESC LIMIT 1
            """,
            (db_user, "email"),
        ).fetchone()
    assert row is not None
    parsed = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    assert abs((parsed - before).total_seconds()) < 5


def test_record_delivery_preserves_valid_iso_timestamps(db_user) -> None:
    record_delivery(
        db_user,
        "aapl-drop",
        "email",
        success=True,
        timestamp="2026-07-24T12:00:00Z",
    )
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT timestamp FROM alert_delivery_log
            WHERE user_id = ? AND channel = ?
            """,
            (db_user, "email"),
        ).fetchone()
    assert row["timestamp"] == "2026-07-24T12:00:00Z"


def test_corrupt_delivery_timestamp_is_not_persisted_verbatim(db_user) -> None:
    """Garbage stamps must not linger as unparseable 'latest' status rows."""
    record_delivery(
        db_user,
        "a1",
        "email",
        success=False,
        error="old",
        timestamp="2026-07-24T10:00:00+00:00",
    )
    before = datetime.now(timezone.utc)
    record_delivery(
        db_user,
        "a1",
        "email",
        success=True,
        test=True,
        timestamp="zzzz",
    )

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, success, test FROM alert_delivery_log
            WHERE user_id = ? AND channel = ?
            ORDER BY id ASC
            """,
            (db_user, "email"),
        ).fetchall()

    assert len(rows) == 2
    assert rows[0]["timestamp"] == "2026-07-24T10:00:00+00:00"
    assert rows[1]["timestamp"] != "zzzz"
    parsed = datetime.fromisoformat(str(rows[1]["timestamp"]).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    assert abs((parsed - before).total_seconds()) < 5

    latest = {row["channel"]: row for row in latest_deliveries_for_user(db_user)}
    assert latest["email"]["timestamp"] == rows[1]["timestamp"]
    assert latest["email"]["success"] is True
    assert latest["email"]["test"] is True

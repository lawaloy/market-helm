"""record_delivery prune must stay per-tenant for a shared alert_id.

The delivery log DELETE keeps the newest MAX_DELIVERY_LOG rows for *this*
user. A missing user_id (or an alert_id-only WHERE) would drop a sibling's
older same-id history while this tenant's status feed grows. Existing prune
tests use a distinct sibling alert_id; #501 covers the newest-per-channel
read path, not this write-side trim.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.storage.alert_watches import (
    MAX_DELIVERY_LOG,
    latest_deliveries_for_user,
    record_delivery,
)
from src.storage.database import get_connection, init_database
from src.storage.users import create_user

ALERT_ID = "aapl-low"
PEER_ERROR = "peer smtp timeout"


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "delivery-prune-tenant.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def _count(user_id: str) -> int:
    with get_connection() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM alert_delivery_log WHERE user_id = ?",
                (user_id,),
            ).fetchone()["n"]
        )


def test_prune_does_not_delete_sibling_rows_for_shared_alert_id(db) -> None:
    """Growing tenant A's aapl-low log must not trim sibling B's older same id."""
    user_a = create_user("prune-tenant-a@example.com", "password123")["id"]
    user_b = create_user("prune-tenant-b@example.com", "password123")["id"]

    record_delivery(
        user_b,
        ALERT_ID,
        "email",
        success=False,
        error=PEER_ERROR,
        timestamp="2026-06-01T00:00:00+00:00",
    )

    base = datetime(2026, 7, 1, tzinfo=timezone.utc)
    for i in range(MAX_DELIVERY_LOG + 5):
        record_delivery(
            user_a,
            ALERT_ID,
            "email",
            success=True,
            timestamp=(base + timedelta(minutes=i)).isoformat(),
        )

    assert _count(user_a) == MAX_DELIVERY_LOG
    assert _count(user_b) == 1

    with get_connection() as conn:
        oldest_a = conn.execute(
            """
            SELECT timestamp FROM alert_delivery_log
            WHERE user_id = ?
            ORDER BY timestamp ASC, id ASC
            LIMIT 1
            """,
            (user_a,),
        ).fetchone()["timestamp"]
        leftover_b = conn.execute(
            """
            SELECT alert_id, channel, success, error, timestamp
            FROM alert_delivery_log
            WHERE user_id = ?
            """,
            (user_b,),
        ).fetchone()

    assert oldest_a == (base + timedelta(minutes=5)).isoformat()
    assert leftover_b["alert_id"] == ALERT_ID
    assert leftover_b["channel"] == "email"
    assert leftover_b["success"] == 0
    assert leftover_b["error"] == PEER_ERROR
    assert leftover_b["timestamp"] == "2026-06-01T00:00:00+00:00"

    latest_a = {row["channel"]: row for row in latest_deliveries_for_user(user_a)}
    latest_b = {row["channel"]: row for row in latest_deliveries_for_user(user_b)}
    assert latest_a["email"]["success"] is True
    assert latest_a["email"]["error"] is None
    assert PEER_ERROR not in str(latest_a)
    assert latest_b["email"]["alert_id"] == ALERT_ID
    assert latest_b["email"]["success"] is False
    assert latest_b["email"]["error"] == PEER_ERROR

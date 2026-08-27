"""latest_deliveries_for_user must be a per-tenant newest-per-channel.

Hosted /api/alerts/status reads this for latest_deliveries. A missing
user_id filter would show another tenant's later send (and their error
text). Existing API tests only assert the empty-sibling case, which
cannot catch leaking a later sibling stamp on the same channel.
"""

from __future__ import annotations

import pytest

from src.storage.alert_watches import latest_deliveries_for_user, record_delivery
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "latest-deliveries.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def test_latest_deliveries_are_newest_per_channel_for_this_user_only(db) -> None:
    """Sibling tenants with later stamps must not leak into this user's latest."""
    user_a = create_user("latest-del-a@example.com", "password123")["id"]
    user_b = create_user("latest-del-b@example.com", "password123")["id"]

    record_delivery(
        user_a,
        "older",
        "email",
        success=False,
        error="smtp timeout",
        timestamp="2026-07-24T10:00:00+00:00",
    )
    record_delivery(
        user_a,
        "newer",
        "email",
        success=True,
        timestamp="2026-07-24T12:00:00+00:00",
    )
    record_delivery(
        user_a,
        "hook",
        "webhook",
        success=True,
        timestamp="2026-07-24T11:00:00+00:00",
    )
    record_delivery(
        user_b,
        "later",
        "email",
        success=False,
        error="peer secret",
        timestamp="2026-07-24T20:00:00+00:00",
    )
    record_delivery(
        user_b,
        "later-hook",
        "webhook",
        success=False,
        error="peer webhook",
        timestamp="2026-07-24T21:00:00+00:00",
    )

    latest_a = {row["channel"]: row for row in latest_deliveries_for_user(user_a)}
    latest_b = {row["channel"]: row for row in latest_deliveries_for_user(user_b)}

    assert set(latest_a) == {"email", "webhook"}
    assert latest_a["email"]["alert_id"] == "newer"
    assert latest_a["email"]["success"] is True
    assert latest_a["email"]["error"] is None
    assert latest_a["email"]["timestamp"] == "2026-07-24T12:00:00+00:00"
    assert latest_a["webhook"]["alert_id"] == "hook"
    assert latest_a["webhook"]["success"] is True
    assert "peer" not in str(latest_a)

    assert set(latest_b) == {"email", "webhook"}
    assert latest_b["email"]["alert_id"] == "later"
    assert latest_b["email"]["error"] == "peer secret"
    assert latest_b["webhook"]["alert_id"] == "later-hook"
    assert latest_b["webhook"]["error"] == "peer webhook"


def test_latest_deliveries_empty_when_user_has_no_rows(db) -> None:
    """Empty tenant must stay empty even when a sibling has later deliveries."""
    user_id = create_user("latest-del-empty@example.com", "password123")["id"]
    sibling = create_user("latest-del-sibling@example.com", "password123")["id"]
    record_delivery(
        sibling,
        "later",
        "email",
        success=False,
        error="peer secret",
        timestamp="2026-07-24T20:00:00+00:00",
    )
    assert latest_deliveries_for_user(user_id) == []

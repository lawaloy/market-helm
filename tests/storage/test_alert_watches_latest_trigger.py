"""latest_trigger_timestamp_for_user must be a per-tenant MAX.

Hosted /api/alerts/status reads this for last_triggered_at. A missing
user_id filter would show another tenant's latest fire; dropping MAX
would pick an arbitrary alert instead of the newest.
"""

from __future__ import annotations

import pytest

from src.storage.alert_watches import (
    latest_trigger_timestamp_for_user,
    record_trigger,
)
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "latest-trigger.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def test_latest_trigger_timestamp_is_max_for_this_user_only(db) -> None:
    """Sibling tenants with later stamps must not leak into this user's MAX."""
    user_a = create_user("latest-a@example.com", "password123")["id"]
    user_b = create_user("latest-b@example.com", "password123")["id"]

    record_trigger(user_a, "older", timestamp="2026-07-24T10:00:00+00:00")
    record_trigger(user_a, "newer", timestamp="2026-07-24T12:00:00+00:00")
    record_trigger(user_b, "later", timestamp="2026-07-24T20:00:00+00:00")

    assert latest_trigger_timestamp_for_user(user_a) == "2026-07-24T12:00:00+00:00"
    assert latest_trigger_timestamp_for_user(user_b) == "2026-07-24T20:00:00+00:00"


def test_latest_trigger_timestamp_none_when_user_has_no_rows(db) -> None:
    user_id = create_user("latest-empty@example.com", "password123")["id"]
    assert latest_trigger_timestamp_for_user(user_id) is None

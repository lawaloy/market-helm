"""Tests for UserAlertStorage cooldown and delivery adapters."""

from datetime import datetime, timezone

import pytest

from src.alerts.user_alert_storage import UserAlertStorage
from src.storage.alert_watches import sync_watches_from_config
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "user_alert_storage.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    user = create_user("storage@example.com", "password123")
    return user["id"]


def _config(alert_id="aapl-drop"):
    return {
        "defaults": {},
        "alerts": [
            {
                "id": alert_id,
                "enabled": True,
                "cooldown_minutes": 30,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "less_than",
                    "value": 200,
                },
                "notifiers": [{"type": "console"}],
            }
        ],
    }


class TestUserAlertStorage:
    def test_get_last_triggered_parses_z_suffix(self, db_user):
        sync_watches_from_config(db_user, _config())
        storage = UserAlertStorage(db_user)
        storage.record_event(
            {"alert_id": "aapl-drop", "timestamp": "2026-07-24T12:00:00Z"}
        )

        got = storage.get_last_triggered("aapl-drop")
        assert got == datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)

    def test_get_last_triggered_returns_none_for_corrupt_marker(self, db_user):
        sync_watches_from_config(db_user, _config())
        storage = UserAlertStorage(db_user)
        storage.record_event({"alert_id": "aapl-drop", "timestamp": "not-a-timestamp"})

        assert storage.get_last_triggered("aapl-drop") is None

    def test_get_last_triggered_returns_none_when_missing(self, db_user):
        sync_watches_from_config(db_user, _config())
        storage = UserAlertStorage(db_user)
        assert storage.get_last_triggered("aapl-drop") is None
        assert storage.latest_event_timestamp() is None

    def test_record_delivery_and_latest_by_channel(self, db_user):
        sync_watches_from_config(db_user, _config())
        storage = UserAlertStorage(db_user)
        storage.record_delivery(
            alert_id="aapl-drop",
            channel="email",
            success=True,
            timestamp="2026-07-24T13:00:00+00:00",
        )
        storage.record_delivery(
            alert_id="aapl-drop",
            channel="webhook",
            success=False,
            error="timeout",
            timestamp="2026-07-24T13:01:00+00:00",
        )

        by_channel = {row["channel"]: row for row in storage.latest_delivery_by_channel()}
        assert by_channel["email"]["success"] is True
        assert by_channel["webhook"]["success"] is False
        assert by_channel["webhook"]["error"] == "timeout"

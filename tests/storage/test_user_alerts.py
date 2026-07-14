"""Unit tests for per-user alert config storage."""

import sqlite3

import pytest

from src.storage.alert_watches import InvalidAlertWatchConfig, list_watches_for_symbol
from src.storage.database import get_connection, init_database
from src.storage.user_alerts import (
    init_user_alerts_config,
    load_user_alerts_config,
    save_user_alerts_config,
)
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    user = create_user("alerts@example.com", "password123")
    return user["id"]


class TestUserAlerts:
    def test_load_missing_config(self, db_user):
        exists, raw = load_user_alerts_config(db_user)
        assert exists is False
        assert raw is None

    def test_init_and_save(self, db_user):
        init_user_alerts_config(db_user)
        exists, raw = load_user_alerts_config(db_user)
        assert exists is True
        assert raw["alerts"] == []

        save_user_alerts_config(
            db_user,
            {
                "defaults": {"email_to": "user@example.com"},
                "alerts": [{"id": "a1", "enabled": True}],
            },
        )
        exists, raw = load_user_alerts_config(db_user)
        assert raw["defaults"]["email_to"] == "user@example.com"
        assert len(raw["alerts"]) == 1

    def test_invalid_watch_config_is_not_persisted(self, db_user):
        with pytest.raises(InvalidAlertWatchConfig):
            save_user_alerts_config(
                db_user,
                {
                    "defaults": {},
                    "alerts": [
                        {
                            "id": "bad-cooldown",
                            "enabled": True,
                            "cooldown_minutes": "later",
                        }
                    ],
                },
            )

        exists, raw = load_user_alerts_config(db_user)
        assert exists is False
        assert raw is None

    def test_watch_sync_failure_rolls_back_config_update(self, db_user):
        original = {
            "defaults": {},
            "alerts": [
                {
                    "id": "original",
                    "enabled": True,
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": "greater_than",
                        "value": 100,
                    },
                }
            ],
        }
        save_user_alerts_config(db_user, original)
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TRIGGER reject_blocked_watch
                BEFORE INSERT ON alert_watches
                WHEN NEW.alert_id = 'blocked'
                BEGIN
                    SELECT RAISE(ABORT, 'blocked watch');
                END
                """
            )

        replacement = {
            "defaults": {},
            "alerts": [
                {
                    "id": "blocked",
                    "enabled": True,
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "MSFT",
                        "operator": "greater_than",
                        "value": 200,
                    },
                }
            ],
        }
        with pytest.raises(sqlite3.IntegrityError, match="blocked watch"):
            save_user_alerts_config(db_user, replacement)

        _, raw = load_user_alerts_config(db_user)
        assert raw == original
        assert list_watches_for_symbol("MSFT") == []
        assert list_watches_for_symbol("AAPL")[0]["alert_id"] == "original"

    def test_init_conflict_without_force(self, db_user):
        init_user_alerts_config(db_user)
        with pytest.raises(FileExistsError):
            init_user_alerts_config(db_user)

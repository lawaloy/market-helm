"""Unit tests for per-user alert config storage."""

import pytest

from src.storage.alert_watches import InvalidAlertWatchConfig
from src.storage.database import init_database
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

    def test_init_conflict_without_force(self, db_user):
        init_user_alerts_config(db_user)
        with pytest.raises(FileExistsError):
            init_user_alerts_config(db_user)

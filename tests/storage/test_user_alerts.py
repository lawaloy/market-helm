"""Unit tests for per-user alert config storage."""

import pytest

from src.storage.alert_watches import InvalidAlertWatchConfig, list_watches_for_symbol
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

    def test_save_preserves_per_alert_webhook_secret_when_update_omits_it(self, db_user):
        alert = {
            "id": "aapl-drop",
            "name": "AAPL drop",
            "enabled": True,
            "notifications": ["webhook"],
            "webhook_url": "https://hooks.example/user/rule-token",
            "condition": {
                "type": "price_threshold",
                "symbol": "AAPL",
                "operator": "less_than",
                "value": 200,
            },
        }
        save_user_alerts_config(db_user, {"defaults": {}, "alerts": [alert]})

        updated_alert = dict(alert)
        updated_alert.pop("webhook_url")
        updated_alert["name"] = "Updated AAPL drop"
        save_user_alerts_config(
            db_user,
            {"defaults": {"email_to": "user@example.com"}, "alerts": [updated_alert]},
        )

        _, raw = load_user_alerts_config(db_user)
        assert raw["alerts"][0]["name"] == "Updated AAPL drop"
        assert raw["alerts"][0]["webhook_url"] == alert["webhook_url"]
        indexed_watch = list_watches_for_symbol("AAPL")[0]
        assert indexed_watch["alert"]["webhook_url"] == alert["webhook_url"]

    def test_init_conflict_without_force(self, db_user):
        init_user_alerts_config(db_user)
        with pytest.raises(FileExistsError):
            init_user_alerts_config(db_user)

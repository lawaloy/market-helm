"""Regression: hosted webhook secrets survive blank/whitespace client updates."""

import pytest

from src.storage.alert_watches import list_watches_for_symbol
from src.storage.database import init_database
from src.storage.user_alerts import load_user_alerts_config, save_user_alerts_config
from src.storage.users import create_user

SECRET = "https://hooks.example/user/secret-token"
REPLACEMENT = "https://hooks.example/user/replacement-token"


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    user = create_user("webhook-preserve@example.com", "password123")
    return user["id"]


def _price_alert(alert_id: str, *, webhook_url: str | None = SECRET) -> dict:
    alert = {
        "id": alert_id,
        "name": "AAPL drop",
        "enabled": True,
        "notifications": ["webhook"],
        "condition": {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": "less_than",
            "value": 150,
        },
    }
    if webhook_url is not None:
        alert["webhook_url"] = webhook_url
    return alert


class TestWebhookSecretPreserve:
    def test_blank_defaults_webhook_preserves_existing_secret(self, db_user):
        save_user_alerts_config(
            db_user,
            {
                "defaults": {"webhook_url": SECRET, "notify_webhook": True},
                "alerts": [],
            },
        )

        save_user_alerts_config(
            db_user,
            {
                "defaults": {
                    "webhook_url": "",
                    "notify_webhook": True,
                    "email_to": "ops@example.com",
                },
                "alerts": [],
            },
        )

        _, raw = load_user_alerts_config(db_user)
        assert raw is not None
        assert raw["defaults"]["webhook_url"] == SECRET
        assert raw["defaults"]["email_to"] == "ops@example.com"

    def test_whitespace_per_alert_webhook_preserves_existing_secret(self, db_user):
        save_user_alerts_config(
            db_user,
            {"defaults": {}, "alerts": [_price_alert("aapl-drop")]},
        )

        updated = _price_alert("aapl-drop", webhook_url="   \t  ")
        updated["name"] = "Renamed"
        save_user_alerts_config(db_user, {"defaults": {}, "alerts": [updated]})

        _, raw = load_user_alerts_config(db_user)
        assert raw is not None
        assert raw["alerts"][0]["name"] == "Renamed"
        assert raw["alerts"][0]["webhook_url"] == SECRET
        indexed = list_watches_for_symbol("AAPL")[0]
        assert indexed["alert"]["webhook_url"] == SECRET

    def test_non_blank_webhook_replaces_existing_secret(self, db_user):
        save_user_alerts_config(
            db_user,
            {
                "defaults": {"webhook_url": SECRET},
                "alerts": [_price_alert("aapl-drop")],
            },
        )

        save_user_alerts_config(
            db_user,
            {
                "defaults": {"webhook_url": f"  {REPLACEMENT}  "},
                "alerts": [_price_alert("aapl-drop", webhook_url=f" {REPLACEMENT} ")],
            },
        )

        _, raw = load_user_alerts_config(db_user)
        assert raw is not None
        assert raw["defaults"]["webhook_url"] == REPLACEMENT
        assert raw["alerts"][0]["webhook_url"] == REPLACEMENT
        indexed = list_watches_for_symbol("AAPL")[0]
        assert indexed["alert"]["webhook_url"] == REPLACEMENT

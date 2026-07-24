"""Non-list notifications must not substring-match or crash delivery."""

from unittest.mock import MagicMock

import pytest

from src.alerts.alert_engine import AlertEngine
from src.alerts.alert_paths import apply_alert_defaults


@pytest.mark.parametrize(
    "bad_notifications",
    ["not_email_channel", "email_webhook_log", 5, True, {"email": True}],
)
def test_apply_alert_defaults_ignores_non_list_notifications(bad_notifications) -> None:
    """Substring membership would wrongly attach defaults.email_to for strings."""
    merged = apply_alert_defaults(
        {"id": "a1", "notifications": bad_notifications},
        {"email_to": "ops@example.com", "webhook_url": "https://hooks.example/x"},
    )
    assert "email_to" not in merged
    assert "webhook_url" not in merged


def test_apply_alert_defaults_seeds_email_for_list_channel() -> None:
    merged = apply_alert_defaults(
        {"id": "a1", "notifications": ["email", "log"]},
        {"email_to": "ops@example.com"},
    )
    assert merged["email_to"] == "ops@example.com"


def test_build_notifiers_tolerates_non_list_notifications() -> None:
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine(
        [
            {
                "id": "bad-notif",
                "name": "Bad notif",
                "enabled": True,
                "notifications": 5,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "greater_than",
                    "value": 100,
                },
            }
        ],
        storage=storage,
        defaults={"email_to": "ops@example.com"},
    )

    events = engine.evaluate([{"symbol": "AAPL", "close": 150.0}])

    assert len(events) == 1
    assert events[0]["alert_id"] == "bad-notif"

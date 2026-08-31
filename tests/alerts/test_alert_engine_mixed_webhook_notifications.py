"""Mixed-type notifications lists must still dispatch webhook.

#548 locked junk-item skip plus log fallback. Treating the whole list as
invalid would silently drop a remaining ``webhook`` channel after junk
items, including defaults.webhook_url and webhook_format seeding.
"""

from unittest.mock import MagicMock, patch

from src.alerts.alert_engine import AlertEngine


def _price_alert(**overrides):
    alert = {
        "id": "watch-1",
        "name": "AAPL up",
        "enabled": True,
        "notifications": ["log"],
        "condition": {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": "greater_than",
            "value": 100,
        },
    }
    alert.update(overrides)
    return alert


def test_evaluate_mixed_notifications_still_dispatches_webhook() -> None:
    """Junk items must not discard a remaining webhook channel or skip defaults."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    webhook = MagicMock()
    engine = AlertEngine(
        [_price_alert(notifications=[1, None, "webhook"])],
        storage=storage,
        defaults={
            "webhook_url": "https://hooks.example/alerts",
            "webhook_format": "slack",
        },
    )

    with patch(
        "src.alerts.alert_engine.WebhookNotifier.from_alert",
        return_value=webhook,
    ) as from_alert:
        events = engine.evaluate([{"symbol": "AAPL", "close": 150.0}])

    assert len(events) == 1
    assert events[0]["alert_id"] == "watch-1"
    from_alert.assert_called_once()
    merged = from_alert.call_args[0][0]
    assert merged["webhook_url"] == "https://hooks.example/alerts"
    assert merged["webhook_format"] == "slack"
    webhook.send.assert_called_once_with(events[0])
    storage.record_event.assert_called_once_with(events[0])

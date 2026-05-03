"""Tests for alert engine notification dispatch."""

from unittest.mock import MagicMock, patch

from src.alerts.alert_engine import AlertEngine


def test_evaluate_dispatches_webhook_notifier_for_triggered_alert():
    """Triggered webhook alerts are persisted and delivered with the engine event payload."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    webhook = MagicMock()
    alert = {
        "id": "price-drop",
        "name": "Price Drop",
        "enabled": True,
        "notifications": ["webhook"],
        "condition": {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": "less_than",
            "value": 150,
        },
    }
    engine = AlertEngine([alert], storage=storage)

    with patch(
        "src.alerts.alert_engine.WebhookNotifier.from_alert", return_value=webhook
    ) as from_alert:
        events = engine.evaluate([{"symbol": "AAPL", "close": 149.5}])

    assert len(events) == 1
    event = events[0]
    assert event["alert_id"] == "price-drop"
    assert event["symbols"] == ["AAPL"]
    storage.record_event.assert_called_once_with(event)
    from_alert.assert_called_once_with(alert)
    webhook.send.assert_called_once_with(event)


def test_evaluate_falls_back_to_log_notifier_when_webhook_is_not_configured():
    """Webhook-only alerts still emit via log fallback when URL resolution fails."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    alert = {
        "id": "volume-spike",
        "notifications": ["webhook"],
        "condition": {
            "type": "screening_match",
            "filters": {"volume_threshold": 1_000_000},
        },
    }
    engine = AlertEngine([alert], storage=storage)

    with patch("src.alerts.alert_engine.WebhookNotifier.from_alert", return_value=None):
        with patch("src.alerts.alert_engine.LogNotifier") as log_notifier_cls:
            log_notifier = log_notifier_cls.return_value
            events = engine.evaluate(
                [
                    {"symbol": "AAPL", "volume": 2_000_000, "change_percent": 0, "close": 100},
                    {"symbol": "MSFT", "volume": 500_000, "change_percent": 0, "close": 100},
                ]
            )

    assert len(events) == 1
    assert events[0]["symbols"] == ["AAPL"]
    log_notifier_cls.assert_called_once_with()
    log_notifier.send.assert_called_once_with(events[0])


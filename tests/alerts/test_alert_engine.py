"""Tests for alert engine notification dispatch."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.alerts.alert_engine import AlertEngine


class InMemoryCooldownStorage:
    def __init__(self):
        self.events = []
        self.last_triggered = None

    def get_last_triggered(self, _alert_id):
        return self.last_triggered

    def record_event(self, event):
        self.events.append(event)
        self.last_triggered = datetime.fromisoformat(event["timestamp"])


def _price_alert(**overrides):
    alert = {
        "id": "aapl-drop",
        "name": "AAPL Drop",
        "enabled": True,
        "cooldown_minutes": 5,
        "condition": {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": "less_than",
            "value": 150,
        },
        "notifications": ["log"],
    }
    alert.update(overrides)
    return alert


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


def test_evaluate_does_not_record_failed_delivery_so_retry_can_fire():
    """Failed notification delivery must not start cooldown or suppress a retry."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    webhook = MagicMock()
    webhook.send.side_effect = [False, True]
    alert = {
        "id": "price-drop",
        "name": "Price Drop",
        "enabled": True,
        "notifications": ["webhook"],
        "cooldown_minutes": 60,
        "condition": {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": "less_than",
            "value": 150,
        },
    }
    engine = AlertEngine([alert], storage=storage)

    with patch("src.alerts.alert_engine.WebhookNotifier.from_alert", return_value=webhook):
        failed_events = engine.evaluate([{"symbol": "AAPL", "close": 149.5}])
        retried_events = engine.evaluate([{"symbol": "AAPL", "close": 149.5}])

    assert failed_events == []
    assert len(retried_events) == 1
    assert webhook.send.call_count == 2
    storage.record_event.assert_called_once_with(retried_events[0])


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


def test_evaluate_falls_back_to_log_notifier_for_unknown_notifier_name():
    """Unknown notification channels must not silently drop a triggered alert."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    alert = {
        "id": "aapl-drop",
        "name": "AAPL Drop",
        "notifications": ["bogus-channel"],
        "condition": {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": "less_than",
            "value": 150,
        },
    }
    engine = AlertEngine([alert], storage=storage)

    with patch("src.alerts.alert_engine.LogNotifier") as log_notifier_cls:
        log_notifier = log_notifier_cls.return_value
        events = engine.evaluate([{"symbol": "AAPL", "close": 149.5}])

    assert len(events) == 1
    assert events[0]["symbols"] == ["AAPL"]
    log_notifier_cls.assert_called_once_with()
    log_notifier.send.assert_called_once_with(events[0])
    storage.record_event.assert_called_once_with(events[0])


def test_evaluate_dispatches_email_notifier_for_triggered_alert():
    """Triggered email alerts are persisted and delivered with the engine event payload."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    email = MagicMock()
    alert = {
        "id": "price-drop",
        "name": "Price Drop",
        "enabled": True,
        "notifications": ["email"],
        "condition": {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": "less_than",
            "value": 150,
        },
    }
    engine = AlertEngine([alert], storage=storage)

    with patch("src.alerts.alert_engine.EmailNotifier.from_alert", return_value=email) as from_alert:
        events = engine.evaluate([{"symbol": "AAPL", "close": 149.5}])

    assert len(events) == 1
    event = events[0]
    from_alert.assert_called_once_with(alert)
    email.send.assert_called_once_with(event)


def test_evaluate_suppresses_duplicate_notifications_during_cooldown():
    """Repeated worker checks must not resend the same alert inside its cooldown window."""
    storage = InMemoryCooldownStorage()
    notifier = MagicMock()
    alert = _price_alert()
    engine = AlertEngine([alert], storage=storage)
    stocks = [{"symbol": "AAPL", "close": 149.5}]
    first_check = datetime(2026, 5, 20, 12, 0, 0)
    second_check = datetime(2026, 5, 20, 12, 1, 0)
    third_check = datetime(2026, 5, 20, 12, 6, 0)

    with patch("src.alerts.alert_engine.LogNotifier", return_value=notifier):
        with patch("src.alerts.alert_engine.datetime") as mock_datetime:
            mock_datetime.utcnow.side_effect = [
                first_check,
                second_check,
                third_check,
                third_check,
            ]
            first_events = engine.evaluate(stocks)
            second_events = engine.evaluate(stocks)
            third_events = engine.evaluate(stocks)

    assert len(first_events) == 1
    assert second_events == []
    assert len(third_events) == 1
    assert len(storage.events) == 2
    assert notifier.send.call_count == 2


def test_evaluate_respects_cooldown_for_timezone_aware_last_triggered():
    """Hosted job-queue markers are timezone-aware; manual rechecks must not TypeError."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = datetime.now(timezone.utc) - timedelta(
        minutes=1
    )
    engine = AlertEngine([_price_alert()], storage=storage)

    with patch("src.alerts.alert_engine.LogNotifier") as log_notifier_cls:
        events = engine.evaluate([{"symbol": "AAPL", "close": 149.5}])

    assert events == []
    log_notifier_cls.assert_not_called()
    storage.record_event.assert_not_called()


def test_evaluate_respects_cooldown_for_naive_last_triggered():
    """File-backed naive markers must keep working after the aware-clock fix."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = datetime.utcnow() - timedelta(minutes=1)
    engine = AlertEngine([_price_alert()], storage=storage)

    events = engine.evaluate([{"symbol": "AAPL", "close": 149.5}])

    assert events == []
    storage.record_event.assert_not_called()


def test_evaluate_fires_again_after_aware_cooldown_expires():
    storage = MagicMock()
    storage.get_last_triggered.return_value = datetime.now(timezone.utc) - timedelta(
        minutes=10
    )
    notifier = MagicMock()
    engine = AlertEngine([_price_alert()], storage=storage)

    with patch("src.alerts.alert_engine.LogNotifier", return_value=notifier):
        events = engine.evaluate([{"symbol": "AAPL", "close": 149.5}])

    assert len(events) == 1
    notifier.send.assert_called_once_with(events[0])
    storage.record_event.assert_called_once_with(events[0])


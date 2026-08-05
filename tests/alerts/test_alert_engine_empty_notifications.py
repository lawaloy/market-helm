"""Empty notifications lists must fall back to log delivery."""

from unittest.mock import MagicMock, patch

from src.alerts.alert_engine import AlertEngine


def test_evaluate_falls_back_to_log_notifier_for_empty_notifications() -> None:
    """Explicit [] is distinct from missing/non-list and must still deliver."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    alert = {
        "id": "empty-channels",
        "name": "Empty channels",
        "enabled": True,
        "notifications": [],
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
    assert events[0]["alert_id"] == "empty-channels"
    log_notifier_cls.assert_called_once_with()
    log_notifier.send.assert_called_once_with(events[0])
    storage.record_event.assert_called_once_with(events[0])

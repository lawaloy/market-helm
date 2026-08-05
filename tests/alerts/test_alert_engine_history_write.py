"""Successful notifier sends must survive alert history write failures."""

from unittest.mock import MagicMock, patch

from src.alerts.alert_engine import AlertEngine


def _price_alert(**overrides):
    alert = {
        "id": "aapl-drop",
        "name": "AAPL Drop",
        "enabled": True,
        "cooldown_minutes": 0,
        "notifications": ["log"],
        "condition": {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": "less_than",
            "value": 150,
        },
    }
    alert.update(overrides)
    return alert


def test_deliver_event_returns_true_when_history_write_fails():
    """OSError after a successful send must not raise or look like delivery failure."""
    storage = MagicMock()
    storage.record_event.side_effect = OSError("disk full")
    notifier = MagicMock()
    notifier.send.return_value = True
    alert = _price_alert()
    event = {
        "alert_id": alert["id"],
        "alert_name": alert["name"],
        "symbols": ["AAPL"],
        "test": False,
    }
    engine = AlertEngine([alert], storage=storage)

    with patch.object(engine, "_build_notifiers", return_value=[notifier]):
        with patch("src.alerts.alert_engine.record_notifier_delivery"):
            delivered = engine.deliver_event(alert, event)

    assert delivered is True
    storage.record_event.assert_called_once_with(event)
    notifier.send.assert_called_once_with(event)


def test_evaluate_continues_when_history_write_fails_for_prior_alert():
    """A history write failure after delivery must not abort sibling watches."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    storage.record_event.side_effect = [OSError("disk full"), None]

    first = _price_alert(id="first", name="AAPL Drop")
    second = _price_alert(
        id="second",
        name="MSFT Drop",
        condition={
            "type": "price_threshold",
            "symbol": "MSFT",
            "operator": "less_than",
            "value": 300,
        },
    )
    engine = AlertEngine([first, second], storage=storage)
    notifier = MagicMock()
    notifier.send.return_value = True

    with patch("src.alerts.alert_engine.LogNotifier", return_value=notifier):
        with patch("src.alerts.alert_engine.record_notifier_delivery"):
            events = engine.evaluate(
                [
                    {"symbol": "AAPL", "close": 140.0},
                    {"symbol": "MSFT", "close": 250.0},
                ]
            )

    assert [event["alert_id"] for event in events] == ["first", "second"]
    assert storage.record_event.call_count == 2

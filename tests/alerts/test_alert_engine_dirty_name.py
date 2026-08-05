"""AlertEngine.evaluate must soft-fail dirty alert names and non-list stocks."""

from unittest.mock import MagicMock

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


def test_evaluate_returns_empty_when_stocks_is_not_a_list() -> None:
    """None/dict stocks previously TypeError'd and aborted the whole check cycle."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine([_price_alert()], storage=storage)

    assert engine.evaluate(None) == []  # type: ignore[arg-type]
    assert engine.evaluate({"symbol": "AAPL", "close": 150.0}) == []  # type: ignore[arg-type]


def test_evaluate_coerces_nan_alert_name_to_alert_id() -> None:
    """Float NaN names stringify to 'nan' and must not leak into notifications."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine(
        [_price_alert(name=float("nan"))],
        storage=storage,
    )

    events = engine.evaluate([{"symbol": "AAPL", "close": 150.0}])

    assert len(events) == 1
    assert events[0]["alert_name"] == "watch-1"
    assert events[0]["alert_name"].lower() != "nan"


def test_evaluate_coerces_sentinel_alert_name_to_alert_id() -> None:
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine(
        [_price_alert(name="None")],
        storage=storage,
    )

    events = engine.evaluate([{"symbol": "AAPL", "close": 150.0}])

    assert len(events) == 1
    assert events[0]["alert_name"] == "watch-1"

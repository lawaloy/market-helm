"""Unsupported price operators must soft-fail without aborting sibling alerts."""

from unittest.mock import MagicMock

from src.alerts.alert_engine import AlertEngine


def _price_alert(alert_id: str, operator: str, value: float = 100):
    return {
        "id": alert_id,
        "name": alert_id,
        "enabled": True,
        "notifications": ["log"],
        "condition": {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": operator,
            "value": value,
        },
    }


def test_evaluate_skips_unsupported_operator_without_aborting_siblings() -> None:
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine(
        [
            _price_alert("bad", "below"),
            _price_alert("good", "greater_than"),
        ],
        storage=storage,
    )

    events = engine.evaluate([{"symbol": "AAPL", "close": 150.0}])

    assert len(events) == 1
    assert events[0]["alert_id"] == "good"
    assert events[0]["symbols"] == ["AAPL"]

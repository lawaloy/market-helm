"""Engine dispatch for RSI and compound conditions."""

from unittest.mock import MagicMock, patch

from src.alerts.alert_engine import AlertEngine


def _falling_closes(n: int = 20, start: float = 100.0) -> list[float]:
    return [start - i for i in range(n)]


def test_engine_triggers_rsi_threshold_with_history():
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    alert = {
        "id": "aapl-rsi",
        "name": "AAPL RSI",
        "enabled": True,
        "notifications": ["log"],
        "condition": {
            "type": "rsi_threshold",
            "symbol": "AAPL",
            "period": 14,
            "operator": "less_than",
            "value": 30,
        },
    }
    engine = AlertEngine([alert], storage=storage)
    with patch(
        "src.alerts.alert_engine.closes_by_symbol",
        return_value={"AAPL": _falling_closes()},
    ):
        events = engine.evaluate([{"symbol": "AAPL", "close": 80.0}])

    assert len(events) == 1
    assert events[0]["condition_type"] == "rsi_threshold"
    assert events[0]["symbols"] == ["AAPL"]
    storage.record_event.assert_called_once()


def test_engine_triggers_compound_and():
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    alert = {
        "id": "aapl-combo",
        "name": "AAPL Combo",
        "enabled": True,
        "notifications": ["log"],
        "condition": {
            "type": "compound",
            "op": "and",
            "conditions": [
                {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "less_than",
                    "value": 150,
                },
                {
                    "type": "rsi_threshold",
                    "symbol": "AAPL",
                    "period": 14,
                    "operator": "less_than",
                    "value": 30,
                },
            ],
        },
    }
    engine = AlertEngine([alert], storage=storage)
    with patch(
        "src.alerts.alert_engine.closes_by_symbol",
        return_value={"AAPL": _falling_closes()},
    ):
        events = engine.evaluate([{"symbol": "AAPL", "close": 140.0}])

    assert len(events) == 1
    assert events[0]["condition_type"] == "compound"

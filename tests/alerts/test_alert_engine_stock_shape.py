"""Non-dict stock rows must not abort AlertEngine.evaluate for siblings."""

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


def _screening_alert(**overrides):
    alert = {
        "id": "screen-1",
        "name": "Volume screen",
        "enabled": True,
        "notifications": ["log"],
        "condition": {
            "type": "screening_match",
            "filters": {"volume_threshold": 1_000_000},
        },
    }
    alert.update(overrides)
    return alert


def test_evaluate_skips_non_dict_stock_rows_for_price_threshold() -> None:
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine([_price_alert()], storage=storage)

    events = engine.evaluate(
        [
            "poison",
            None,
            ["AAPL", 150],
            {"symbol": "AAPL", "close": 150.0},
        ]
    )

    assert len(events) == 1
    assert events[0]["alert_id"] == "watch-1"
    assert events[0]["symbols"] == ["AAPL"]


def test_evaluate_skips_non_dict_stock_rows_for_screening_match() -> None:
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine([_screening_alert()], storage=storage)

    events = engine.evaluate(
        [
            "poison",
            {"symbol": "MSFT", "volume": 2_000_000, "close": 40},
            None,
        ]
    )

    assert len(events) == 1
    assert events[0]["symbols"] == ["MSFT"]

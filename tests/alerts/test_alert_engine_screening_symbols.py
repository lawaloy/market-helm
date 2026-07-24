"""screening_match events must emit normalized tickers only."""

from unittest.mock import MagicMock

from src.alerts.alert_engine import AlertEngine


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


def test_screening_match_normalizes_padded_symbols() -> None:
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine([_screening_alert()], storage=storage)

    events = engine.evaluate(
        [
            {
                "symbol": " aapl ",
                "volume": 2_000_000,
                "change_percent": 1.0,
                "close": 100,
            }
        ]
    )

    assert len(events) == 1
    assert events[0]["symbols"] == ["AAPL"]


def test_screening_match_drops_none_and_nan_symbols() -> None:
    """None/NaN symbols must not leak into notification payloads."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine([_screening_alert()], storage=storage)

    events = engine.evaluate(
        [
            {
                "symbol": None,
                "volume": 5_000_000,
                "change_percent": 2.0,
                "close": 50,
            },
            {
                "symbol": float("nan"),
                "volume": 5_000_000,
                "change_percent": 2.0,
                "close": 50,
            },
            {
                "symbol": "MSFT",
                "volume": 5_000_000,
                "change_percent": 2.0,
                "close": 50,
            },
        ]
    )

    assert len(events) == 1
    assert events[0]["symbols"] == ["MSFT"]


def test_screening_match_skips_alert_when_all_symbols_invalid() -> None:
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine([_screening_alert()], storage=storage)

    events = engine.evaluate(
        [
            {
                "symbol": None,
                "volume": 5_000_000,
                "change_percent": 2.0,
                "close": 50,
            },
            {
                "symbol": "NAN",
                "volume": 5_000_000,
                "change_percent": 2.0,
                "close": 50,
            },
        ]
    )

    assert events == []
    storage.record_event.assert_not_called()

"""Mixed-type notifications lists must not abort AlertEngine.evaluate.

Non-list ``notifications`` already fall back to log. A hand-edited *list*
with junk items takes the iterate-and-skip path instead, and used to be
untested: a TypeError in ``_build_notifiers`` would drop sibling watches
in the same check cycle.
"""

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


def test_evaluate_skips_hashable_junk_channels_and_still_delivers() -> None:
    """[1, None, True, "log"] is a list, so junk must skip and log still send."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine(
        [_price_alert(notifications=[1, None, True, "log"])],
        storage=storage,
    )

    events = engine.evaluate([{"symbol": "AAPL", "close": 150.0}])

    assert len(events) == 1
    assert events[0]["alert_id"] == "watch-1"
    storage.record_event.assert_called_once_with(events[0])


def test_evaluate_mixed_junk_notifications_do_not_abort_sibling() -> None:
    """All-junk mixed list falls back to log and must not skip a later watch."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine(
        [
            _price_alert(id="poison", notifications=[1, None, True]),
            _price_alert(
                id="keep",
                condition={
                    "type": "price_threshold",
                    "symbol": "MSFT",
                    "operator": "greater_than",
                    "value": 100,
                },
            ),
        ],
        storage=storage,
    )

    events = engine.evaluate(
        [
            {"symbol": "AAPL", "close": 150.0},
            {"symbol": "MSFT", "close": 150.0},
        ]
    )

    assert [event["alert_id"] for event in events] == ["poison", "keep"]
    assert events[0]["symbols"] == ["AAPL"]
    assert events[1]["symbols"] == ["MSFT"]
    assert storage.record_event.call_count == 2

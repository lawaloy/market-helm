"""Missing/blank alert ids must soft-fail without aborting sibling watches."""

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


def test_from_config_dict_skips_enabled_alerts_without_id() -> None:
    engine = AlertEngine.from_config_dict(
        {
            "alerts": [
                _price_alert(id="ok"),
                {
                    "enabled": True,
                    "notifications": ["log"],
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "MSFT",
                        "operator": "greater_than",
                        "value": 1,
                    },
                },
                _price_alert(id="  ", enabled=True),
                _price_alert(id=None, enabled=True),
            ],
        }
    )
    assert engine is not None
    assert [a["id"] for a in engine.alerts] == ["ok"]


def test_evaluate_skips_missing_id_and_still_fires_sibling() -> None:
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    bad = {
        "enabled": True,
        "notifications": ["log"],
        "condition": {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": "greater_than",
            "value": 100,
        },
    }
    engine = AlertEngine(
        [bad, _price_alert(id="good", condition={
            "type": "price_threshold",
            "symbol": "MSFT",
            "operator": "greater_than",
            "value": 100,
        })],
        storage=storage,
    )

    events = engine.evaluate(
        [
            {"symbol": "AAPL", "close": 150.0},
            {"symbol": "MSFT", "close": 150.0},
        ]
    )

    assert len(events) == 1
    assert events[0]["alert_id"] == "good"
    assert events[0]["symbols"] == ["MSFT"]


def test_evaluate_skips_none_and_blank_ids() -> None:
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine(
        [
            _price_alert(id=None),
            _price_alert(id="   "),
            _price_alert(id="keep"),
        ],
        storage=storage,
    )

    events = engine.evaluate([{"symbol": "AAPL", "close": 150.0}])

    assert len(events) == 1
    assert events[0]["alert_id"] == "keep"

"""AlertEngine must soft-fail hand-edited / corrupt alerts.json shapes."""

import json
from pathlib import Path
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


def test_from_config_dict_returns_none_for_non_object_root() -> None:
    assert AlertEngine.from_config_dict(["not", "a", "dict"]) is None
    assert AlertEngine.from_config_dict("alerts") is None
    assert AlertEngine.from_config_dict(None) is None  # type: ignore[arg-type]


def test_from_config_dict_skips_non_dict_alert_rows() -> None:
    engine = AlertEngine.from_config_dict(
        {
            "defaults": "junk",
            "alerts": [
                "broken",
                None,
                _price_alert(id="ok", enabled=True),
                {"id": "off", "enabled": False, "condition": {}},
            ],
        }
    )
    assert engine is not None
    assert len(engine.alerts) == 1
    assert engine.alerts[0]["id"] == "ok"
    assert engine.defaults == {}


def test_from_config_returns_none_for_list_rooted_file(tmp_path: Path) -> None:
    path = tmp_path / "alerts.json"
    path.write_text(json.dumps(["x"]), encoding="utf-8")
    assert AlertEngine.from_config(path) is None


def test_evaluate_skips_non_dict_condition_without_aborting_siblings() -> None:
    storage = MagicMock()
    storage.get_last_triggered.return_value = None
    engine = AlertEngine(
        [
            _price_alert(id="bad", condition="nope"),
            _price_alert(id="good", condition={
                "type": "price_threshold",
                "symbol": "AAPL",
                "operator": "greater_than",
                "value": 100,
            }),
        ],
        storage=storage,
    )

    events = engine.evaluate([{"symbol": "AAPL", "close": 150.0}])

    assert len(events) == 1
    assert events[0]["alert_id"] == "good"
    assert events[0]["symbols"] == ["AAPL"]

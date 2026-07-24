"""Non-finite cooldown_minutes must soft-fail, not abort sibling evaluation."""

from datetime import datetime, timezone
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


def test_within_cooldown_treats_inf_as_no_cooldown() -> None:
    storage = MagicMock()
    storage.get_last_triggered.return_value = datetime.now(timezone.utc)
    engine = AlertEngine([], storage=storage)

    assert engine._within_cooldown(
        {"id": "bad", "cooldown_minutes": float("inf")}
    ) is False
    assert engine._within_cooldown(
        {"id": "bad-neg", "cooldown_minutes": float("-inf")}
    ) is False


def test_evaluate_continues_after_inf_cooldown_on_sibling() -> None:
    """Inf cooldown soft-fails to no cooldown; siblings still evaluate."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = datetime.now(timezone.utc)
    engine = AlertEngine(
        [
            _price_alert(id="poison", cooldown_minutes=float("inf")),
            _price_alert(
                id="good",
                cooldown_minutes=0,
                condition={
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "greater_than",
                    "value": 100,
                },
            ),
        ],
        storage=storage,
    )

    events = engine.evaluate([{"symbol": "AAPL", "close": 150.0}])

    assert {e["alert_id"] for e in events} == {"poison", "good"}

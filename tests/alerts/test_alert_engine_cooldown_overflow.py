"""Huge finite cooldown must soft-fail in evaluators — not abort sibling watches."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.alerts.alert_engine import AlertEngine
from src.alerts.job_processor import _within_cooldown


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


def test_engine_within_cooldown_overflow_treats_as_cooling() -> None:
    storage = MagicMock()
    storage.get_last_triggered.return_value = datetime.now(timezone.utc)
    engine = AlertEngine([], storage=storage)

    assert engine._within_cooldown(
        {"id": "poison", "cooldown_minutes": 10**15}
    ) is True


def test_engine_evaluate_continues_after_huge_cooldown_sibling() -> None:
    """Overflow cooldown soft-fails to in-cooldown; good sibling still fires."""
    storage = MagicMock()
    storage.get_last_triggered.return_value = datetime.now(timezone.utc)
    engine = AlertEngine(
        [
            _price_alert(id="poison", cooldown_minutes=10**15),
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

    assert {e["alert_id"] for e in events} == {"good"}


def test_job_processor_within_cooldown_overflow_treats_as_cooling() -> None:
    with patch("src.alerts.job_processor.UserAlertStorage") as storage_cls:
        storage = storage_cls.return_value
        storage.get_last_triggered.return_value = datetime.now(timezone.utc)
        assert _within_cooldown("user-1", "alert-1", 10**15) is True

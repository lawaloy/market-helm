"""Huge finite cooldown_minutes must be rejected / clamped — not OverflowError."""

import pytest

from src.storage.alert_watches import (
    MAX_COOLDOWN_MINUTES,
    InvalidAlertWatchConfig,
    _safe_cooldown_minutes,
    validate_watches_config,
)
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "cooldown-ceiling.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("cooldown-ceiling@example.com", "password123")["id"]


def _price_alert(**overrides):
    alert = {
        "id": "aapl-low",
        "enabled": True,
        "condition": {
            "type": "price_threshold",
            "symbol": "AAPL",
            "operator": "less_than",
            "value": 200,
        },
    }
    alert.update(overrides)
    return alert


@pytest.mark.parametrize("bad", [1e15, 10**15, MAX_COOLDOWN_MINUTES + 1])
def test_validate_rejects_huge_cooldown(db_user, bad) -> None:
    with pytest.raises(InvalidAlertWatchConfig, match="invalid cooldown_minutes"):
        validate_watches_config(
            db_user,
            {"defaults": {}, "alerts": [_price_alert(cooldown_minutes=bad)]},
        )


def test_validate_accepts_cooldown_at_ceiling(db_user) -> None:
    validate_watches_config(
        db_user,
        {
            "defaults": {},
            "alerts": [_price_alert(cooldown_minutes=MAX_COOLDOWN_MINUTES)],
        },
    )


def test_safe_cooldown_clamps_huge_values() -> None:
    assert _safe_cooldown_minutes(1e15) == MAX_COOLDOWN_MINUTES
    assert _safe_cooldown_minutes(MAX_COOLDOWN_MINUTES + 99) == MAX_COOLDOWN_MINUTES
    assert _safe_cooldown_minutes(15) == 15
    assert _safe_cooldown_minutes(-5) == 0

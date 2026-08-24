"""Stored Inf/NaN cooldown text must clamp to 0 without aborting sibling watches."""

from __future__ import annotations

import math

import pytest

from src.storage.alert_watches import (
    _safe_cooldown_minutes,
    get_watch,
    list_watches_for_symbol,
    sync_watches_from_config,
)
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_users(tmp_path, monkeypatch):
    db_path = tmp_path / "cooldown-inf.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    good = create_user("cooldown-inf-good@example.com", "password123")["id"]
    bad = create_user("cooldown-inf-bad@example.com", "password123")["id"]
    return good, bad


def _price_config(alert_id: str) -> dict:
    return {
        "defaults": {},
        "alerts": [
            {
                "id": alert_id,
                "enabled": True,
                "cooldown_minutes": 15,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "less_than",
                    "value": 200,
                },
            }
        ],
    }


@pytest.mark.parametrize(
    "poison",
    [float("inf"), float("-inf"), float("nan"), "inf", "-inf", "nan", "Infinity"],
)
def test_safe_cooldown_returns_zero_for_nonfinite_values(poison) -> None:
    """float('inf') succeeds; isfinite must catch it before timedelta OverflowError."""
    assert _safe_cooldown_minutes(poison) == 0


@pytest.mark.parametrize("poison", ["inf", "-inf", "nan", "Infinity"])
def test_list_watches_clamps_nonfinite_cooldown_text_without_dropping_siblings(
    db_users, poison
) -> None:
    good_user, bad_user = db_users
    sync_watches_from_config(good_user, _price_config("keep"))
    sync_watches_from_config(bad_user, _price_config("poison"))
    with get_connection() as conn:
        conn.execute(
            "UPDATE alert_watches SET cooldown_minutes = ? WHERE user_id = ? AND alert_id = ?",
            (poison, bad_user, "poison"),
        )

    watches = {watch["user_id"]: watch for watch in list_watches_for_symbol("AAPL")}
    assert set(watches) == {good_user, bad_user}
    assert watches[bad_user]["cooldown_minutes"] == 0
    assert watches[good_user]["cooldown_minutes"] == 15
    loaded = get_watch(bad_user, "poison")
    assert loaded is not None
    assert loaded["cooldown_minutes"] == 0
    assert math.isfinite(watches[bad_user]["cooldown_minutes"])

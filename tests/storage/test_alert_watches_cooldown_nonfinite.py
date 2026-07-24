"""Inf/NaN cooldown_minutes must raise InvalidAlertWatchConfig, not OverflowError."""

import json

import pytest

from src.storage.alert_watches import (
    InvalidAlertWatchConfig,
    get_watch,
    list_watches_for_symbol,
    sync_watches_from_config,
    validate_watches_config,
)
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "cooldown.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("cooldown@example.com", "password123")["id"]


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


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_validate_rejects_nonfinite_cooldown(db_user, bad) -> None:
    with pytest.raises(InvalidAlertWatchConfig, match="invalid cooldown_minutes"):
        validate_watches_config(
            db_user,
            {"defaults": {}, "alerts": [_price_alert(cooldown_minutes=bad)]},
        )


def test_backfill_skips_inf_cooldown_without_crashing(db_user) -> None:
    """OverflowError used to escape InvalidAlertWatchConfig and abort init_database."""
    poison = {
        "defaults": {},
        "alerts": [_price_alert(cooldown_minutes=float("inf"))],
    }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_alert_configs (user_id, config_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (db_user, json.dumps(poison, allow_nan=True), "2026-07-24T00:00:00+00:00"),
        )

    init_database()
    assert list_watches_for_symbol("AAPL") == []


def test_list_watches_skips_non_dict_alert_json(db_user) -> None:
    sync_watches_from_config(
        db_user,
        {"defaults": {}, "alerts": [_price_alert(cooldown_minutes=5)]},
    )
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE alert_watches
            SET alert_json = ?, defaults_json = ?
            WHERE user_id = ? AND alert_id = ?
            """,
            (json.dumps(["not", "a", "dict"]), json.dumps(["bad"]), db_user, "aapl-low"),
        )

    assert list_watches_for_symbol("AAPL") == []
    assert get_watch(db_user, "aapl-low") is None

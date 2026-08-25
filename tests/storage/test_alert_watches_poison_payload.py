"""Evaluate-path watch index must skip poison JSON / cooldown without dropping siblings."""

import json

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
    db_path = tmp_path / "poison-payload.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    good = create_user("poison-good@example.com", "password123")["id"]
    bad = create_user("poison-bad@example.com", "password123")["id"]
    return good, bad


def _price_config(alert_id: str = "aapl-low"):
    return {
        "defaults": {"email_to": "user@example.com"},
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


def _sync_pair(good_user: str, bad_user: str) -> None:
    sync_watches_from_config(good_user, _price_config("keep"))
    sync_watches_from_config(bad_user, _price_config("poison"))


def test_list_watches_skips_unparseable_alert_json_without_dropping_siblings(
    db_users,
) -> None:
    """JSONDecodeError used to be untested; one tenant's junk must not abort fan-out."""
    good_user, bad_user = db_users
    _sync_pair(good_user, bad_user)
    with get_connection() as conn:
        conn.execute(
            "UPDATE alert_watches SET alert_json = ? WHERE user_id = ? AND alert_id = ?",
            ("{not-json", bad_user, "poison"),
        )

    watches = list_watches_for_symbol("AAPL")
    assert [w["user_id"] for w in watches] == [good_user]
    assert watches[0]["alert_id"] == "keep"
    assert get_watch(bad_user, "poison") is None


def test_list_watches_skips_unparseable_defaults_json_without_dropping_siblings(
    db_users,
) -> None:
    """alert_json and defaults_json share one parse; poison defaults skip the row."""
    good_user, bad_user = db_users
    _sync_pair(good_user, bad_user)
    with get_connection() as conn:
        conn.execute(
            "UPDATE alert_watches SET defaults_json = ? WHERE user_id = ? AND alert_id = ?",
            ("{not-json", bad_user, "poison"),
        )

    watches = list_watches_for_symbol("AAPL")
    assert [w["user_id"] for w in watches] == [good_user]
    assert get_watch(bad_user, "poison") is None


def test_list_watches_keeps_watch_when_defaults_json_is_a_non_object(db_users) -> None:
    """Valid JSON that is not an object must not drop the alert; defaults fall back to {}."""
    good_user, _bad_user = db_users
    sync_watches_from_config(good_user, _price_config("keep"))
    with get_connection() as conn:
        conn.execute(
            "UPDATE alert_watches SET defaults_json = ? WHERE user_id = ? AND alert_id = ?",
            (json.dumps(["not", "an", "object"]), good_user, "keep"),
        )

    watches = list_watches_for_symbol("AAPL")
    assert len(watches) == 1
    assert watches[0]["defaults"] == {}
    assert watches[0]["alert"]["id"] == "keep"
    loaded = get_watch(good_user, "keep")
    assert loaded is not None
    assert loaded["defaults"] == {}


@pytest.mark.parametrize("poison", ["not-a-number", "zzzz", object()])
def test_safe_cooldown_returns_zero_for_unparseable_values(poison) -> None:
    """Poison DB / caller values must not OverflowError or TypeError the watch loop."""
    assert _safe_cooldown_minutes(poison) == 0


def test_list_watches_clamps_poison_cooldown_text_without_dropping_siblings(
    db_users,
) -> None:
    good_user, bad_user = db_users
    _sync_pair(good_user, bad_user)
    with get_connection() as conn:
        conn.execute(
            "UPDATE alert_watches SET cooldown_minutes = ? WHERE user_id = ? AND alert_id = ?",
            ("not-a-number", bad_user, "poison"),
        )

    watches = {w["user_id"]: w for w in list_watches_for_symbol("AAPL")}
    assert set(watches) == {good_user, bad_user}
    assert watches[bad_user]["cooldown_minutes"] == 0
    assert watches[good_user]["cooldown_minutes"] == 15

"""Watch sync/backfill must skip blank/missing alert ids without dropping siblings."""

import json

import pytest

from src.storage.alert_watches import (
    list_enabled_symbols,
    list_watches_for_symbol,
    sync_watches_from_config,
)
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_users(tmp_path, monkeypatch):
    db_path = tmp_path / "blank-id-sync.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    mixed = create_user("blank-id-mixed@example.com", "password123")["id"]
    sibling = create_user("blank-id-sibling@example.com", "password123")["id"]
    return mixed, sibling


def _price_alert(alert_id, symbol: str = "AAPL", **overrides):
    alert = {
        "id": alert_id,
        "enabled": True,
        "condition": {
            "type": "price_threshold",
            "symbol": symbol,
            "operator": "less_than",
            "value": 200,
        },
    }
    alert.update(overrides)
    return alert


def test_sync_skips_blank_and_missing_ids_without_dropping_siblings(db_users) -> None:
    mixed_user, sibling_user = db_users
    sync_watches_from_config(
        mixed_user,
        {
            "defaults": {},
            "alerts": [
                _price_alert(None, symbol="AAPL"),
                _price_alert("   ", symbol="MSFT"),
                _price_alert("", symbol="NFLX"),
                _price_alert("keep-goog", symbol="GOOG"),
            ],
        },
    )
    sync_watches_from_config(
        sibling_user,
        {
            "defaults": {},
            "alerts": [_price_alert("sibling-aapl", symbol="AAPL")],
        },
    )

    assert list_enabled_symbols() == ["AAPL", "GOOG"]
    goog = list_watches_for_symbol("GOOG")
    assert [(w["user_id"], w["alert_id"]) for w in goog] == [
        (mixed_user, "keep-goog")
    ]
    aapl = list_watches_for_symbol("AAPL")
    assert [(w["user_id"], w["alert_id"]) for w in aapl] == [
        (sibling_user, "sibling-aapl")
    ]
    assert list_watches_for_symbol("MSFT") == []
    assert list_watches_for_symbol("NFLX") == []


def test_backfill_skips_blank_ids_without_dropping_sibling_watches(db_users) -> None:
    mixed_user, sibling_user = db_users
    sync_watches_from_config(
        sibling_user,
        {
            "defaults": {},
            "alerts": [_price_alert("sibling-msft", symbol="MSFT")],
        },
    )
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_alert_configs (user_id, config_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (
                mixed_user,
                json.dumps(
                    {
                        "defaults": {},
                        "alerts": [
                            _price_alert("  ", symbol="AAPL"),
                            _price_alert("keep-nflx", symbol="NFLX"),
                        ],
                    }
                ),
                "2026-07-24T00:00:00+00:00",
            ),
        )

    init_database()

    assert sorted(list_enabled_symbols()) == ["MSFT", "NFLX"]
    assert [w["alert_id"] for w in list_watches_for_symbol("NFLX")] == ["keep-nflx"]
    assert [w["alert_id"] for w in list_watches_for_symbol("MSFT")] == ["sibling-msft"]
    assert list_watches_for_symbol("AAPL") == []

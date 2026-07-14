"""Unit tests for normalized alert watches."""

import json

import pytest

from src.storage.alert_watches import (
    list_enabled_symbols,
    list_watches_for_symbol,
    sync_watches_from_config,
)
from src.storage.database import get_connection, init_database
from src.storage.user_alerts import save_user_alerts_config
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "watches.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    user = create_user("watches@example.com", "password123")
    return user["id"]


def _sample_config():
    return {
        "defaults": {"email_to": "user@example.com"},
        "alerts": [
            {
                "id": "aapl-drop",
                "name": "AAPL drop",
                "enabled": True,
                "cooldown_minutes": 30,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "less_than",
                    "value": 200,
                },
                "notifiers": [{"type": "console"}],
            },
            {
                "id": "msft-disabled",
                "enabled": False,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "MSFT",
                    "operator": "greater_than",
                    "value": 100,
                },
            },
        ],
    }


class TestAlertWatches:
    def test_sync_on_save(self, db_user):
        save_user_alerts_config(db_user, _sample_config())
        assert list_enabled_symbols() == ["AAPL"]
        watches = list_watches_for_symbol("AAPL")
        assert len(watches) == 1
        assert watches[0]["user_id"] == db_user
        assert watches[0]["alert_id"] == "aapl-drop"

    def test_symbol_index_dedupes_symbols_but_keeps_each_user_watch(self, db_user):
        other_user = create_user("other-watches@example.com", "password123")["id"]
        save_user_alerts_config(db_user, _sample_config())
        save_user_alerts_config(
            other_user,
            {
                "defaults": {"email_to": "other@example.com"},
                "alerts": [
                    {
                        "id": "aapl-rise",
                        "enabled": True,
                        "cooldown_minutes": 5,
                        "condition": {
                            "type": "price_threshold",
                            "symbol": "aapl",
                            "operator": "greater_than",
                            "value": 150,
                        },
                    },
                    {
                        "id": "goog-disabled",
                        "enabled": False,
                        "condition": {
                            "type": "price_threshold",
                            "symbol": "GOOG",
                            "operator": "greater_than",
                            "value": 100,
                        },
                    },
                ],
            },
        )

        assert list_enabled_symbols() == ["AAPL"]

        watches = list_watches_for_symbol("aapl")
        assert {(watch["user_id"], watch["alert_id"]) for watch in watches} == {
            (db_user, "aapl-drop"),
            (other_user, "aapl-rise"),
        }

    def test_sync_replaces_rows(self, db_user):
        save_user_alerts_config(db_user, _sample_config())
        save_user_alerts_config(db_user, {"defaults": {}, "alerts": []})
        assert list_enabled_symbols() == []
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM alert_watches WHERE user_id = ?",
                (db_user,),
            ).fetchone()["n"]
        assert count == 0

    def test_backfill_on_init_database(self, db_user, tmp_path, monkeypatch):
        save_user_alerts_config(db_user, _sample_config())
        db_path = tmp_path / "watches.db"
        init_database()
        assert list_enabled_symbols() == ["AAPL"]

    def test_backfill_skips_invalid_config_rows(self, db_user):
        bad_config = {
            "defaults": {},
            "alerts": [
                {
                    "id": "bad-price",
                    "enabled": True,
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": "below",
                        "value": "not-a-number",
                    },
                }
            ],
        }
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_alert_configs (user_id, config_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (db_user, json.dumps(bad_config), "2026-07-12T00:00:00+00:00"),
            )

        init_database()

        assert list_enabled_symbols() == []

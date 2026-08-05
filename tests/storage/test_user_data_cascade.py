"""Deleting a user must cascade tenant alert rows (FK + PRAGMA foreign_keys)."""

from __future__ import annotations

import json

import pytest

from src.storage.alert_watches import sync_watches_from_config
from src.storage.database import get_connection, init_database
from src.storage.user_alerts import save_user_alerts_config
from src.storage.users import create_user


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "cascade.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "test-secret-min-16-chars")
    init_database()
    return db_path


def test_delete_user_cascades_alert_tenant_tables(db) -> None:
    user = create_user("cascade@example.com", "password123")
    user_id = user["id"]
    config = {
        "defaults": {},
        "alerts": [
            {
                "id": "aapl_watch",
                "enabled": True,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "less_than",
                    "value": 150,
                },
                "cooldown_minutes": 30,
            }
        ],
    }
    save_user_alerts_config(user_id, config)
    sync_watches_from_config(user_id, config)

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO alert_trigger_state (user_id, alert_id, last_triggered_at) "
            "VALUES (?, ?, ?)",
            (user_id, "aapl_watch", "2026-01-01T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO alert_delivery_log "
            "(user_id, alert_id, channel, success, test, error, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                "aapl_watch",
                "email",
                1,
                0,
                None,
                "2026-01-01T00:00:00+00:00",
            ),
        )

    with get_connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM user_alert_configs WHERE user_id = ?",
            (user_id,),
        ).fetchone()["n"] == 1
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM alert_watches WHERE user_id = ?",
            (user_id,),
        ).fetchone()["n"] == 1
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM alert_trigger_state WHERE user_id = ?",
            (user_id,),
        ).fetchone()["n"] == 1
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM alert_delivery_log WHERE user_id = ?",
            (user_id,),
        ).fetchone()["n"] == 1

    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    with get_connection() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) AS n FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) AS n FROM user_alert_configs WHERE user_id = ?",
                (user_id,),
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) AS n FROM alert_watches WHERE user_id = ?",
                (user_id,),
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) AS n FROM alert_trigger_state WHERE user_id = ?",
                (user_id,),
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) AS n FROM alert_delivery_log WHERE user_id = ?",
                (user_id,),
            ).fetchone()["n"]
            == 0
        )


def test_delete_user_does_not_remove_other_tenant_rows(db) -> None:
    kept = create_user("kept@example.com", "password123")
    gone = create_user("gone@example.com", "password123")
    config = {
        "defaults": {},
        "alerts": [
            {
                "id": "msft",
                "enabled": True,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "MSFT",
                    "operator": "greater_than",
                    "value": 1,
                },
            }
        ],
    }
    save_user_alerts_config(kept["id"], config)
    save_user_alerts_config(gone["id"], config)
    sync_watches_from_config(kept["id"], config)
    sync_watches_from_config(gone["id"], config)

    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (gone["id"],))

    with get_connection() as conn:
        cfg = conn.execute(
            "SELECT config_json FROM user_alert_configs WHERE user_id = ?",
            (kept["id"],),
        ).fetchone()
        assert cfg is not None
        assert json.loads(cfg["config_json"])["alerts"][0]["id"] == "msft"
        assert (
            conn.execute(
                "SELECT COUNT(*) AS n FROM alert_watches WHERE user_id = ?",
                (kept["id"],),
            ).fetchone()["n"]
            == 1
        )

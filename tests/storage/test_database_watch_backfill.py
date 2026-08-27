"""Watch backfill during init_database must skip unparseable configs without aborting."""

import threading
from concurrent.futures import ThreadPoolExecutor

from src.storage.alert_watches import (
    list_enabled_symbols,
    list_watches_for_symbol,
    sync_watches_from_config,
)
from src.storage.database import get_connection, init_database
from src.storage.user_alerts import load_user_alerts_config, save_user_alerts_config
from src.storage.users import create_user


def _price_config(alert_id: str, symbol: str) -> dict:
    return {
        "defaults": {},
        "alerts": [
            {
                "id": alert_id,
                "name": alert_id,
                "enabled": True,
                "condition": {
                    "type": "price_threshold",
                    "symbol": symbol,
                    "operator": "less_than",
                    "value": 150,
                },
                "notifications": ["log"],
            }
        ],
    }


def test_backfill_skips_unparseable_json_and_keeps_sibling_watches(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "backfill-json.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    good_user = create_user("backfill-good@example.com", "password123")["id"]
    bad_user = create_user("backfill-bad@example.com", "password123")["id"]
    sync_watches_from_config(
        good_user,
        {
            "defaults": {},
            "alerts": [
                {
                    "id": "aapl-low",
                    "enabled": True,
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": "less_than",
                        "value": 200,
                    },
                }
            ],
        },
    )
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_alert_configs (user_id, config_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (bad_user, "{not-json", "2026-07-24T00:00:00+00:00"),
        )

    init_database()

    assert list_enabled_symbols() == ["AAPL"]


def test_stale_backfill_cannot_restore_watches_over_newer_save(
    tmp_path, monkeypatch
) -> None:
    """Worker/login init_database must not revive watches a concurrent save replaced.

    Backfill used to SELECT every config, drop the connection, then rewrite
    watches from that snapshot. A Settings save in the gap commits the new
    config+watches; the stale sync then restores the old enabled rows so the
    next orchestrator tick can fire a pause/delete/retarget the user already
    persisted.
    """
    db_path = tmp_path / "backfill-race.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    user_id = create_user("backfill-race@example.com", "password123")["id"]
    save_user_alerts_config(user_id, _price_config("aapl_drop", "AAPL"))
    assert list_enabled_symbols() == ["AAPL"]

    barrier = threading.Barrier(2)
    import src.storage.alert_watches as alert_watches

    original_sync = alert_watches.sync_watches_from_config

    def delayed_sync(*args, **kwargs):
        # Pause after backfill has already read config_json so a save can commit.
        # save_user_alerts_config binds sync at import time and is not delayed.
        barrier.wait(timeout=5)
        return original_sync(*args, **kwargs)

    monkeypatch.setattr(alert_watches, "sync_watches_from_config", delayed_sync)

    def do_backfill() -> None:
        init_database()

    def do_save() -> None:
        barrier.wait(timeout=5)
        save_user_alerts_config(user_id, _price_config("goog_drop", "GOOG"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(do_backfill), pool.submit(do_save)]
        for future in futures:
            future.result(timeout=30)

    _, raw = load_user_alerts_config(user_id)
    assert raw is not None
    assert [alert["id"] for alert in raw["alerts"]] == ["goog_drop"]
    assert list_enabled_symbols() == ["GOOG"]
    assert {(w["user_id"], w["alert_id"]) for w in list_watches_for_symbol("GOOG")} == {
        (user_id, "goog_drop")
    }
    assert list_watches_for_symbol("AAPL") == []

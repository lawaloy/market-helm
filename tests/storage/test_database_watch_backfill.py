"""Watch backfill during init_database must skip unparseable configs without aborting."""

from src.storage.alert_watches import list_enabled_symbols, sync_watches_from_config
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


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

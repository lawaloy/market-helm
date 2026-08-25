"""evaluate_symbol must skip non-price watches without aborting sibling tenants."""

from unittest.mock import patch

import pytest

from src.alerts.job_processor import process_job_queue
from src.storage.alert_jobs import JOB_DELIVER, JOB_EVALUATE_SYMBOL, enqueue_job, pending_job_count
from src.storage.alert_watches import sync_watches_from_config
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "processor-condition-type.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("cond-type@example.com", "password123")["id"]


def _watch_config(alert_id: str = "aapl-low"):
    return {
        "defaults": {},
        "alerts": [
            {
                "id": alert_id,
                "name": "AAPL low",
                "enabled": True,
                "cooldown_minutes": 0,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "less_than",
                    "value": 200,
                },
                "notifiers": [{"type": "console"}],
            }
        ],
    }


def test_evaluate_skips_non_price_threshold_without_blocking_siblings(db_user) -> None:
    """Poisoned condition_type still sits on the symbol index; siblings must still notify."""
    bad_user = create_user("cond-type-bad@example.com", "password123")["id"]
    sync_watches_from_config(bad_user, _watch_config("screening"))
    sync_watches_from_config(db_user, _watch_config("aapl-low"))

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE alert_watches
            SET condition_type = ?
            WHERE user_id = ? AND alert_id = ?
            """,
            ("screening_match", bad_user, "screening"),
        )

    enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 150.0})

    with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True):
        stats = process_job_queue("test-worker")

    assert stats["evaluated"] == 1
    assert stats["delivered"] == 1
    assert stats["failed"] == 0
    assert pending_job_count([JOB_DELIVER]) == 0
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT user_id, alert_id FROM alert_trigger_state"
        ).fetchall()
    assert {(row["user_id"], row["alert_id"]) for row in rows} == {
        (db_user, "aapl-low"),
    }

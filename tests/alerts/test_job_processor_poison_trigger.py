"""Deliver jobs must fail closed on unparseable stored trigger markers."""

from unittest.mock import patch

import pytest

from src.alerts.job_processor import process_job_queue
from src.storage.alert_jobs import JOB_DELIVER, enqueue_job, pending_job_count
from src.storage.alert_watches import get_last_triggered, sync_watches_from_config
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_users(tmp_path, monkeypatch):
    db_path = tmp_path / "poison-trigger.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    poison = create_user("poison-trigger@example.com", "password123")["id"]
    sibling = create_user("sibling-trigger@example.com", "password123")["id"]
    return poison, sibling


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


def _event(user_id: str, alert_id: str, timestamp: str = "2026-07-24T13:00:00+00:00"):
    return {
        "alert_id": alert_id,
        "alert_name": "AAPL low",
        "symbols": ["AAPL"],
        "timestamp": timestamp,
        "condition_type": "price_threshold",
        "user_id": user_id,
    }


def test_deliver_skips_unparseable_trigger_row_without_blocking_sibling(
    db_users,
) -> None:
    """A poison last_triggered_at must complete without send; siblings still notify."""
    poison_user, sibling_user = db_users
    sync_watches_from_config(poison_user, _watch_config("poison"))
    sync_watches_from_config(sibling_user, _watch_config("keep"))

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO alert_trigger_state (user_id, alert_id, last_triggered_at)
            VALUES (?, ?, ?)
            """,
            (poison_user, "poison", "zzzz"),
        )

    poison_job = enqueue_job(
        JOB_DELIVER,
        {
            "user_id": poison_user,
            "alert_id": "poison",
            "event": _event(poison_user, "poison"),
        },
    )
    sibling_job = enqueue_job(
        JOB_DELIVER,
        {
            "user_id": sibling_user,
            "alert_id": "keep",
            "event": _event(sibling_user, "keep"),
        },
    )

    with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True) as mock_send:
        stats = process_job_queue("test-worker")

    assert stats == {"evaluated": 0, "delivered": 1, "failed": 0}
    assert mock_send.call_count == 1
    assert pending_job_count([JOB_DELIVER]) == 0
    assert get_last_triggered(poison_user, "poison") == "zzzz"
    assert get_last_triggered(sibling_user, "keep") == "2026-07-24T13:00:00+00:00"

    with get_connection() as conn:
        rows = {
            int(row["id"]): row["status"]
            for row in conn.execute(
                "SELECT id, status FROM alert_jobs WHERE id IN (?, ?)",
                (poison_job, sibling_job),
            ).fetchall()
        }
    assert rows[poison_job] == "completed"
    assert rows[sibling_job] == "completed"

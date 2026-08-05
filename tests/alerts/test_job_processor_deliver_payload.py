"""Malformed deliver jobs must soft-complete — not retry-churn the queue."""

from unittest.mock import patch

import pytest

from src.alerts.job_processor import process_job_queue
from src.storage.alert_jobs import (
    JOB_DELIVER,
    JOB_EVALUATE_SYMBOL,
    enqueue_job,
    pending_job_count,
)
from src.storage.alert_watches import sync_watches_from_config
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "deliver-payload.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("deliver-payload@example.com", "password123")["id"]


def _watch_config():
    return {
        "defaults": {},
        "alerts": [
            {
                "id": "aapl-low",
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


@pytest.mark.parametrize(
    "poison_payload",
    [
        {"alert_id": "aapl-low", "event": {"symbol": "AAPL", "price": 150}},
        {"user_id": "u", "event": {"symbol": "AAPL", "price": 150}},
        {"user_id": "u", "alert_id": "aapl-low"},
        {"user_id": "u", "alert_id": "aapl-low", "event": ["not", "a", "dict"]},
        {"user_id": "u", "alert_id": "aapl-low", "event": None},
    ],
)
def test_poison_deliver_payload_completes_without_retry(
    db_user, poison_payload
) -> None:
    """Missing keys / non-dict event must drain once (no fail→retry loop)."""
    sync_watches_from_config(db_user, _watch_config())
    poison_id = enqueue_job(JOB_DELIVER, poison_payload, max_attempts=5)

    stats = process_job_queue("test-worker")

    assert stats["failed"] == 0
    assert pending_job_count([JOB_DELIVER]) == 0
    with get_connection() as conn:
        poison = conn.execute(
            "SELECT status, attempts, last_error FROM alert_jobs WHERE id = ?",
            (poison_id,),
        ).fetchone()
    assert poison["status"] == "completed"
    assert int(poison["attempts"]) == 1


def test_poison_deliver_still_processes_sibling_jobs(db_user) -> None:
    sync_watches_from_config(db_user, _watch_config())
    enqueue_job(
        JOB_DELIVER,
        {"alert_id": "aapl-low", "event": {"symbol": "AAPL"}},  # missing user_id
        max_attempts=5,
    )
    enqueue_job(
        JOB_EVALUATE_SYMBOL,
        {"symbol": "AAPL", "price": 150.0, "tick_id": "ok"},
    )

    with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True):
        stats = process_job_queue("test-worker")

    assert stats["evaluated"] == 1
    assert stats["delivered"] == 1
    assert stats["failed"] == 0
    assert pending_job_count([JOB_DELIVER, JOB_EVALUATE_SYMBOL]) == 0

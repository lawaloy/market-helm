"""Stale deliver retries must not redelivery when event timestamp is missing/invalid."""

from unittest.mock import patch

import pytest

from src.alerts.job_processor import _process_deliver, process_job_queue
from src.storage.alert_jobs import JOB_DELIVER, STATUS_COMPLETED, claim_jobs, enqueue_job
from src.storage.alert_watches import sync_watches_from_config
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "stale-ts.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    user = create_user("stale-ts@example.com", "password123")
    return user["id"]


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
    "timestamp",
    [None, "", "not-a-timestamp", "2026-13-99T99:99:99Z"],
)
def test_stale_retry_skips_when_event_timestamp_unusable(db_user, timestamp) -> None:
    """Prior successful trigger + retry must skip even without a parseable event_at."""
    sync_watches_from_config(db_user, _watch_config())
    event = {
        "alert_id": "aapl-low",
        "alert_name": "AAPL low",
        "symbols": ["AAPL"],
        "condition_type": "price_threshold",
        "user_id": db_user,
    }
    if timestamp is not None:
        event["timestamp"] = timestamp

    job_id = enqueue_job(
        JOB_DELIVER,
        {"user_id": db_user, "alert_id": "aapl-low", "event": event},
    )
    claimed = claim_jobs([JOB_DELIVER], "first-attempt")
    assert claimed[0]["id"] == job_id

    with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True) as mock_send:
        # First attempt has no last_triggered yet — deliver once.
        assert _process_deliver(claimed[0]) is True
        assert mock_send.call_count == 1

        with get_connection() as conn:
            conn.execute(
                "UPDATE alert_jobs SET locked_at = ? WHERE id = ?",
                ("2000-01-01T00:00:00+00:00", job_id),
            )

        stats = process_job_queue("recovery-worker")

    assert stats == {"evaluated": 0, "delivered": 0, "failed": 0}
    assert mock_send.call_count == 1
    with get_connection() as conn:
        job = conn.execute(
            "SELECT status, attempts FROM alert_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    assert job["status"] == STATUS_COMPLETED
    assert job["attempts"] == 2


def test_stale_retry_still_delivers_when_no_prior_trigger(db_user) -> None:
    """Missing timestamp must not skip a genuine first successful recovery."""
    sync_watches_from_config(db_user, _watch_config())
    event = {
        "alert_id": "aapl-low",
        "alert_name": "AAPL low",
        "symbols": ["AAPL"],
        "condition_type": "price_threshold",
        "user_id": db_user,
        # No timestamp — but no last_triggered either.
    }
    job_id = enqueue_job(
        JOB_DELIVER,
        {"user_id": db_user, "alert_id": "aapl-low", "event": event},
    )
    claimed = claim_jobs([JOB_DELIVER], "crashed-before-send")
    assert claimed[0]["id"] == job_id
    # Simulate crash before deliver: mark job stale without recording a trigger.
    with get_connection() as conn:
        conn.execute(
            "UPDATE alert_jobs SET locked_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00+00:00", job_id),
        )

    with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True) as mock_send:
        stats = process_job_queue("recovery-worker")

    assert stats == {"evaluated": 0, "delivered": 1, "failed": 0}
    assert mock_send.call_count == 1

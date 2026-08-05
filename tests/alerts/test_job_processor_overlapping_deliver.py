"""Overlapping stale recovery must not double-deliver when the original worker resumes."""

from unittest.mock import patch

import pytest

from src.alerts.job_processor import _process_deliver
from src.storage.alert_jobs import JOB_DELIVER, claim_jobs, enqueue_job
from src.storage.alert_watches import get_last_triggered, sync_watches_from_config
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "overlap-deliver.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    user = create_user("overlap@example.com", "password123")
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


def test_late_original_worker_does_not_redeliver_after_recovery(db_user) -> None:
    """Worker A still holding attempts==1 must skip after worker B already delivered."""
    sync_watches_from_config(db_user, _watch_config())
    event = {
        "alert_id": "aapl-low",
        "alert_name": "AAPL low",
        "symbols": ["AAPL"],
        "timestamp": "2026-06-09T12:00:00Z",
        "condition_type": "price_threshold",
        "user_id": db_user,
    }
    job_id = enqueue_job(
        JOB_DELIVER,
        {"user_id": db_user, "alert_id": "aapl-low", "event": event},
    )

    worker_a_jobs = claim_jobs([JOB_DELIVER], "worker-a")
    assert len(worker_a_jobs) == 1
    assert worker_a_jobs[0]["attempts"] == 1

    with get_connection() as conn:
        conn.execute(
            "UPDATE alert_jobs SET locked_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00+00:00", job_id),
        )

    worker_b_jobs = claim_jobs([JOB_DELIVER], "worker-b")
    assert len(worker_b_jobs) == 1
    assert worker_b_jobs[0]["attempts"] == 2

    with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True) as mock_send:
        assert _process_deliver(worker_b_jobs[0]) is True
        assert mock_send.call_count == 1
        trigger_after_b = get_last_triggered(db_user, "aapl-low")
        assert trigger_after_b is not None

        # Original worker resumes with stale in-memory claim (attempts still 1).
        assert worker_a_jobs[0]["attempts"] == 1
        assert _process_deliver(worker_a_jobs[0]) is False
        assert mock_send.call_count == 1
        assert get_last_triggered(db_user, "aapl-low") == trigger_after_b

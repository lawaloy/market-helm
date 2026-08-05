"""Concurrent deliver workers must not double-notify under a positive cooldown."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.alerts.job_processor import _process_deliver
from src.storage.alert_jobs import JOB_DELIVER, enqueue_job
from src.storage.alert_watches import get_last_triggered, sync_watches_from_config
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "concurrent-deliver.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("concurrent-deliver@example.com", "password123")["id"]


def _watch_config(cooldown_minutes: int):
    return {
        "defaults": {},
        "alerts": [
            {
                "id": "aapl-low",
                "name": "AAPL low",
                "enabled": True,
                "cooldown_minutes": cooldown_minutes,
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


def test_concurrent_deliver_jobs_notify_once_under_cooldown(db_user) -> None:
    """Two workers past the pre-send reads must still single-notify via claim."""
    sync_watches_from_config(db_user, _watch_config(cooldown_minutes=60))
    base = datetime.now(timezone.utc)
    event_a = {
        "alert_id": "aapl-low",
        "alert_name": "AAPL low",
        "symbols": ["AAPL"],
        "timestamp": base.isoformat(),
        "condition_type": "price_threshold",
        "user_id": db_user,
    }
    event_b = {
        **event_a,
        "timestamp": (base + timedelta(seconds=1)).isoformat(),
    }
    job_a = {
        "id": enqueue_job(
            JOB_DELIVER,
            {"user_id": db_user, "alert_id": "aapl-low", "event": event_a},
        ),
        "attempts": 1,
        "payload": {"user_id": db_user, "alert_id": "aapl-low", "event": event_a},
    }
    job_b = {
        "id": enqueue_job(
            JOB_DELIVER,
            {"user_id": db_user, "alert_id": "aapl-low", "event": event_b},
        ),
        "attempts": 1,
        "payload": {"user_id": db_user, "alert_id": "aapl-low", "event": event_b},
    }

    barrier = threading.Barrier(2)
    results: list[bool] = []
    lock = threading.Lock()

    def racing_deliver(job):
        barrier.wait(timeout=5)
        return _process_deliver(job)

    with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True) as mock_send:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(racing_deliver, job_a),
                pool.submit(racing_deliver, job_b),
            ]
            for future in futures:
                with lock:
                    results.append(future.result(timeout=10))

    assert sorted(results) == [False, True]
    assert mock_send.call_count == 1
    assert get_last_triggered(db_user, "aapl-low") is not None


def test_failed_concurrent_claim_restores_trigger_for_retry(db_user) -> None:
    """A claimed delivery that fails to notify must clear the claim."""
    sync_watches_from_config(db_user, _watch_config(cooldown_minutes=60))
    event = {
        "alert_id": "aapl-low",
        "alert_name": "AAPL low",
        "symbols": ["AAPL"],
        "timestamp": "2026-06-09T12:00:00+00:00",
        "condition_type": "price_threshold",
        "user_id": db_user,
    }
    job = {
        "id": enqueue_job(
            JOB_DELIVER,
            {"user_id": db_user, "alert_id": "aapl-low", "event": event},
        ),
        "attempts": 1,
        "payload": {"user_id": db_user, "alert_id": "aapl-low", "event": event},
    }

    with patch("src.alerts.alert_engine.LogNotifier.send", return_value=False):
        with pytest.raises(RuntimeError, match="Delivery failed"):
            _process_deliver(job)

    assert get_last_triggered(db_user, "aapl-low") is None

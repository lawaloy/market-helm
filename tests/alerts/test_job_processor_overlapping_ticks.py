"""Overlapping evaluate jobs must not double-deliver under a positive cooldown."""

from unittest.mock import patch

import pytest

from src.alerts.job_processor import process_job_queue
from src.storage.alert_jobs import JOB_EVALUATE_SYMBOL, enqueue_job, pending_job_count
from src.storage.alert_watches import get_last_triggered, sync_watches_from_config
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "overlap-ticks.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("overlap-ticks@example.com", "password123")["id"]


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


def test_overlapping_evaluates_deliver_once_under_cooldown(db_user) -> None:
    """Two evaluate jobs claimed before either deliver records a trigger.

    Without a deliver-time cooldown re-check, both would notify.
    """
    sync_watches_from_config(db_user, _watch_config(cooldown_minutes=60))
    enqueue_job(
        JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 150.0, "tick_id": "t1"}
    )
    enqueue_job(
        JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 149.0, "tick_id": "t2"}
    )

    with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True) as mock_send:
        stats = process_job_queue("overlap-worker")

    assert stats["evaluated"] == 2
    assert stats["delivered"] == 1
    assert stats["failed"] == 0
    assert mock_send.call_count == 1
    assert get_last_triggered(db_user, "aapl-low") is not None
    assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 0


def test_overlapping_evaluates_still_multi_deliver_with_zero_cooldown(db_user) -> None:
    """cooldown_minutes=0 intentionally disables rate limiting."""
    sync_watches_from_config(db_user, _watch_config(cooldown_minutes=0))
    enqueue_job(
        JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 150.0, "tick_id": "t1"}
    )
    enqueue_job(
        JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 149.0, "tick_id": "t2"}
    )

    with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True) as mock_send:
        stats = process_job_queue("overlap-worker-zero")

    assert stats["evaluated"] == 2
    assert stats["delivered"] == 2
    assert mock_send.call_count == 2

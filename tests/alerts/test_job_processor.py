"""Tests for alert job processor (evaluate + deliver)."""

from unittest.mock import patch

import pytest

from src.alerts.job_processor import process_job_queue
from src.storage.alert_jobs import (
    JOB_DELIVER,
    JOB_EVALUATE_SYMBOL,
    enqueue_job,
    pending_job_count,
)
from src.storage.alert_watches import record_trigger, sync_watches_from_config
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "processor.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    user = create_user("proc@example.com", "password123")
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


class TestJobProcessor:
    def test_evaluate_enqueues_and_processes_deliver(self, db_user):
        sync_watches_from_config(db_user, _watch_config())
        enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 150.0, "tick_id": "t1"})

        with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True):
            stats = process_job_queue("test-worker")

        assert stats["evaluated"] == 1
        assert stats["delivered"] == 1
        assert stats["failed"] == 0
        assert pending_job_count([JOB_DELIVER]) == 0

    def test_process_job_queue_drains_ready_jobs_beyond_limit(self, db_user):
        sync_watches_from_config(db_user, _watch_config())
        for index in range(3):
            enqueue_job(
                JOB_EVALUATE_SYMBOL,
                {"symbol": "AAPL", "price": 150.0, "tick_id": f"t{index}"},
            )

        with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True):
            stats = process_job_queue("test-worker", limit=2)

        assert stats["evaluated"] == 3
        assert stats["delivered"] == 3
        assert stats["failed"] == 0
        assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 0
        assert pending_job_count([JOB_DELIVER]) == 0

    def test_deliver_records_trigger(self, db_user):
        sync_watches_from_config(db_user, _watch_config())
        event = {
            "alert_id": "aapl-low",
            "alert_name": "AAPL low",
            "symbols": ["AAPL"],
            "timestamp": "2026-06-09T12:00:00+00:00",
            "condition_type": "price_threshold",
            "user_id": db_user,
        }
        enqueue_job(
            JOB_DELIVER,
            {"user_id": db_user, "alert_id": "aapl-low", "event": event},
        )

        with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True):
            stats = process_job_queue("test-worker")

        assert stats["delivered"] == 1
        with get_connection() as conn:
            row = conn.execute(
                "SELECT last_triggered_at FROM alert_trigger_state WHERE user_id = ? AND alert_id = ?",
                (db_user, "aapl-low"),
            ).fetchone()
        assert row is not None

    def test_evaluate_skips_cooldown(self, db_user):
        config = _watch_config()
        config["alerts"][0]["cooldown_minutes"] = 60
        sync_watches_from_config(db_user, config)
        record_trigger(db_user, "aapl-low")
        enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 150.0})

        stats = process_job_queue("test-worker")
        assert stats["evaluated"] == 1
        assert pending_job_count([JOB_DELIVER]) == 0

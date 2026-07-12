"""Tests for alert job processor (evaluate + deliver)."""

from unittest.mock import patch

import pytest

from src.alerts.job_processor import process_job_queue
from src.storage.alert_jobs import (
    JOB_DELIVER,
    JOB_EVALUATE_SYMBOL,
    STATUS_FAILED,
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

    def test_evaluate_fans_out_deliveries_for_all_users_watching_symbol(self, db_user):
        other_user = create_user("other-proc@example.com", "password123")["id"]
        sync_watches_from_config(db_user, _watch_config())
        other_config = _watch_config()
        other_config["alerts"][0]["id"] = "other-aapl-low"
        sync_watches_from_config(other_user, other_config)
        enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 150.0, "tick_id": "t1"})

        with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True):
            stats = process_job_queue("test-worker")

        assert stats["evaluated"] == 1
        assert stats["delivered"] == 2
        assert stats["failed"] == 0
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT user_id, alert_id FROM alert_trigger_state
                ORDER BY user_id, alert_id
                """
            ).fetchall()
        assert {(row["user_id"], row["alert_id"]) for row in rows} == {
            (db_user, "aapl-low"),
            (other_user, "other-aapl-low"),
        }

    def test_evaluate_does_not_deliver_when_threshold_not_met(self, db_user):
        sync_watches_from_config(db_user, _watch_config())
        enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 250.0, "tick_id": "t1"})

        stats = process_job_queue("test-worker")

        assert stats["evaluated"] == 1
        assert stats["delivered"] == 0
        assert stats["failed"] == 0
        assert pending_job_count([JOB_DELIVER]) == 0
        with get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM alert_trigger_state").fetchone()
        assert row["n"] == 0

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

    def test_failed_delivery_does_not_record_trigger(self, db_user):
        sync_watches_from_config(db_user, _watch_config())
        event = {
            "alert_id": "aapl-low",
            "alert_name": "AAPL low",
            "symbols": ["AAPL"],
            "timestamp": "2026-06-09T12:00:00+00:00",
            "condition_type": "price_threshold",
            "user_id": db_user,
        }
        job_id = enqueue_job(
            JOB_DELIVER,
            {"user_id": db_user, "alert_id": "aapl-low", "event": event},
            max_attempts=1,
        )

        with patch("src.alerts.alert_engine.LogNotifier.send", return_value=False):
            stats = process_job_queue("test-worker")

        assert stats["delivered"] == 0
        assert stats["failed"] == 1
        with get_connection() as conn:
            trigger = conn.execute(
                "SELECT last_triggered_at FROM alert_trigger_state WHERE user_id = ? AND alert_id = ?",
                (db_user, "aapl-low"),
            ).fetchone()
            job = conn.execute(
                "SELECT status, last_error FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert trigger is None
        assert job["status"] == STATUS_FAILED
        assert "Delivery failed" in job["last_error"]

    def test_evaluate_skips_cooldown(self, db_user):
        config = _watch_config()
        config["alerts"][0]["cooldown_minutes"] = 60
        sync_watches_from_config(db_user, config)
        record_trigger(db_user, "aapl-low")
        enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 150.0})

        stats = process_job_queue("test-worker")
        assert stats["evaluated"] == 1
        assert pending_job_count([JOB_DELIVER]) == 0

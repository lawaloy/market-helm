"""Evaluate jobs that raise must fail_job, not complete, and must not block siblings."""

from unittest.mock import patch

import pytest

from src.alerts import job_processor as jp
from src.alerts.job_processor import process_job_queue
from src.storage.alert_jobs import (
    JOB_DELIVER,
    JOB_EVALUATE_SYMBOL,
    STATUS_COMPLETED,
    STATUS_FAILED,
    enqueue_job,
    pending_job_count,
)
from src.storage.alert_watches import sync_watches_from_config
from src.storage.database import get_connection, init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "evaluate-exception.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("eval-exc@example.com", "password123")["id"]


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


def test_evaluate_exception_fails_job_without_completing_or_blocking_sibling(db_user):
    """Unexpected evaluate errors must fail_job; a sibling evaluate still completes."""
    sync_watches_from_config(db_user, _watch_config())
    boom_id = enqueue_job(
        JOB_EVALUATE_SYMBOL,
        {"symbol": "AAPL", "price": 150.0, "tick_id": "boom"},
        max_attempts=1,
    )
    ok_id = enqueue_job(
        JOB_EVALUATE_SYMBOL,
        {"symbol": "AAPL", "price": 150.0, "tick_id": "ok"},
    )

    real = jp._process_evaluate_symbol

    def boom_then_real(job):
        if job["payload"].get("tick_id") == "boom":
            raise RuntimeError("evaluate storage failed")
        return real(job)

    with patch.object(jp, "_process_evaluate_symbol", side_effect=boom_then_real):
        with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True):
            stats = process_job_queue("test-worker")

    assert stats["evaluated"] == 1
    assert stats["failed"] == 1
    assert stats["delivered"] == 1
    assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 0

    with get_connection() as conn:
        boom = conn.execute(
            "SELECT status, last_error FROM alert_jobs WHERE id = ?",
            (boom_id,),
        ).fetchone()
        ok = conn.execute(
            "SELECT status FROM alert_jobs WHERE id = ?",
            (ok_id,),
        ).fetchone()
    assert boom["status"] == STATUS_FAILED
    assert "evaluate storage failed" in boom["last_error"]
    assert ok["status"] == STATUS_COMPLETED
    assert pending_job_count([JOB_DELIVER]) == 0

"""Unit tests for alert job queue."""

import pytest

from src.storage.alert_jobs import (
    JOB_DELIVER,
    JOB_EVALUATE_SYMBOL,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    claim_jobs,
    complete_job,
    enqueue_job,
    fail_job,
    pending_job_count,
)
from src.storage.database import get_connection, init_database


@pytest.fixture
def db(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


class TestAlertJobs:
    def test_enqueue_and_claim(self, db):
        job_id = enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 150.0})
        assert job_id == 1
        assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 1

        claimed = claim_jobs([JOB_EVALUATE_SYMBOL], "worker-a", limit=5)
        assert len(claimed) == 1
        assert claimed[0]["id"] == job_id
        assert claimed[0]["payload"]["symbol"] == "AAPL"
        assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 0

    def test_complete_job(self, db):
        job_id = enqueue_job(JOB_DELIVER, {"user_id": "u1", "alert_id": "a1"})
        claim_jobs([JOB_DELIVER], "worker-b")
        complete_job(job_id)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_COMPLETED

    def test_fail_job_retries_then_fails(self, db):
        job_id = enqueue_job(
            JOB_EVALUATE_SYMBOL,
            {"symbol": "MSFT"},
            max_attempts=2,
        )
        claim_jobs([JOB_EVALUATE_SYMBOL], "worker-c")
        fail_job(job_id, "transient error", retry_delay_seconds=0)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, attempts FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_PENDING
        assert row["attempts"] == 1

        claim_jobs([JOB_EVALUATE_SYMBOL], "worker-c")
        fail_job(job_id, "permanent error", retry_delay_seconds=0)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_FAILED

"""Unit tests for alert job queue."""

from datetime import datetime, timedelta, timezone

import pytest

from src.storage.alert_jobs import (
    JOB_DELIVER,
    JOB_EVALUATE_SYMBOL,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
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

    def test_fail_job_missing_id_is_noop(self, db):
        fail_job(99999, "gone")

    def test_fail_job_truncates_error_to_500_chars(self, db):
        job_id = enqueue_job(
            JOB_EVALUATE_SYMBOL,
            {"symbol": "MSFT"},
            max_attempts=1,
        )
        claim_jobs([JOB_EVALUATE_SYMBOL], "worker-c")
        fail_job(job_id, "e" * 600, retry_delay_seconds=0)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, last_error FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_FAILED
        assert row["last_error"] == "e" * 500

    def test_claim_recovers_stale_processing_job(self, db):
        job_id = enqueue_job(JOB_DELIVER, {"user_id": "u1", "alert_id": "a1"})
        claim_jobs([JOB_DELIVER], "worker-a")
        stale_locked_at = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        with get_connection() as conn:
            conn.execute(
                "UPDATE alert_jobs SET locked_at = ? WHERE id = ?",
                (stale_locked_at, job_id),
            )

        claimed = claim_jobs(
            [JOB_DELIVER],
            "worker-b",
            stale_after_seconds=60,
        )

        assert [job["id"] for job in claimed] == [job_id]
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, attempts, locked_by FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_PROCESSING
        assert row["attempts"] == 2
        assert row["locked_by"] == "worker-b"

    def test_stale_processing_job_fails_after_max_attempts(self, db):
        job_id = enqueue_job(
            JOB_DELIVER,
            {"user_id": "u1", "alert_id": "a1"},
            max_attempts=1,
        )
        claim_jobs([JOB_DELIVER], "worker-a")
        stale_locked_at = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        with get_connection() as conn:
            conn.execute(
                "UPDATE alert_jobs SET locked_at = ? WHERE id = ?",
                (stale_locked_at, job_id),
            )

        claimed = claim_jobs(
            [JOB_DELIVER],
            "worker-b",
            stale_after_seconds=60,
        )

        assert claimed == []
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, locked_at, locked_by, last_error FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_FAILED
        assert row["locked_at"] is None
        assert row["locked_by"] is None
        assert row["last_error"] == "Processing lock expired after max attempts"

    def test_claim_jobs_skips_jobs_until_run_after(self, db):
        job_id = enqueue_job(
            JOB_EVALUATE_SYMBOL,
            {"symbol": "MSFT"},
            max_attempts=2,
        )
        assert claim_jobs([JOB_EVALUATE_SYMBOL], "worker-c") != []

        fail_job(job_id, "transient error", retry_delay_seconds=3600)

        assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 0
        assert claim_jobs([JOB_EVALUATE_SYMBOL], "worker-d") == []
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, attempts FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_PENDING
        assert row["attempts"] == 1

    def test_claim_jobs_marks_corrupt_payload_failed_and_claims_peers(self, db):
        """Corrupt payload_json must not poison the claim transaction/queue."""
        good_id = enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 150.0})
        poison_id = enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": "MSFT", "price": 300.0})
        with get_connection() as conn:
            conn.execute(
                "UPDATE alert_jobs SET payload_json = ? WHERE id = ?",
                ("{not-json", poison_id),
            )

        claimed = claim_jobs([JOB_EVALUATE_SYMBOL], "worker-poison", limit=5)

        assert [job["id"] for job in claimed] == [good_id]
        assert claimed[0]["payload"]["symbol"] == "AAPL"
        with get_connection() as conn:
            poison = conn.execute(
                "SELECT status, last_error, locked_at, locked_by FROM alert_jobs WHERE id = ?",
                (poison_id,),
            ).fetchone()
            good = conn.execute(
                "SELECT status FROM alert_jobs WHERE id = ?",
                (good_id,),
            ).fetchone()
        assert poison["status"] == STATUS_FAILED
        assert poison["locked_at"] is None
        assert poison["locked_by"] is None
        assert "Invalid job payload" in poison["last_error"]
        assert good["status"] == STATUS_PROCESSING

        # Subsequent claims must not re-raise on the failed poison row.
        assert claim_jobs([JOB_EVALUATE_SYMBOL], "worker-poison-2", limit=5) == []

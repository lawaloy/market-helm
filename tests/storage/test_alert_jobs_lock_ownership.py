"""Regression: late workers must not overwrite reclaimed job outcomes."""

from datetime import datetime, timedelta, timezone

import pytest

from src.storage.alert_jobs import (
    JOB_DELIVER,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    claim_jobs,
    complete_job,
    enqueue_job,
    fail_job,
)
from src.storage.database import get_connection, init_database


@pytest.fixture
def db(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs-lock.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def _stale_lock(job_id: int, *, minutes: int = 10) -> None:
    stale_locked_at = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE alert_jobs SET locked_at = ? WHERE id = ?",
            (stale_locked_at, job_id),
        )


class TestAlertJobLockOwnership:
    def test_late_complete_does_not_overwrite_reclaimed_completion(self, db):
        """Original worker completes after reclaim+complete → must be a no-op."""
        job_id = enqueue_job(JOB_DELIVER, {"user_id": "u1", "alert_id": "a1"})
        claim_jobs([JOB_DELIVER], "worker-a")
        _stale_lock(job_id)

        claimed = claim_jobs([JOB_DELIVER], "worker-b", stale_after_seconds=60)
        assert [job["id"] for job in claimed] == [job_id]
        assert complete_job(job_id, worker_id="worker-b") is True

        assert complete_job(job_id, worker_id="worker-a") is False
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, locked_by FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_COMPLETED
        assert row["locked_by"] is None

    def test_late_fail_does_not_requeue_after_reclaimed_completion(self, db):
        """Stale fail must not turn a completed job back into pending."""
        job_id = enqueue_job(
            JOB_DELIVER,
            {"user_id": "u1", "alert_id": "a1"},
            max_attempts=5,
        )
        claim_jobs([JOB_DELIVER], "worker-a")
        _stale_lock(job_id)

        claimed = claim_jobs([JOB_DELIVER], "worker-b", stale_after_seconds=60)
        assert [job["id"] for job in claimed] == [job_id]
        assert complete_job(job_id, worker_id="worker-b") is True

        assert (
            fail_job(
                job_id,
                "late original failure",
                worker_id="worker-a",
                retry_delay_seconds=0,
            )
            is False
        )
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, last_error FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_COMPLETED
        assert row["last_error"] is None

    def test_late_complete_does_not_overwrite_reclaimed_failure(self, db):
        """Stale complete must not resurrect a permanently failed job."""
        job_id = enqueue_job(
            JOB_DELIVER,
            {"user_id": "u1", "alert_id": "a1"},
            max_attempts=2,
        )
        claim_jobs([JOB_DELIVER], "worker-a")
        _stale_lock(job_id)

        claimed = claim_jobs([JOB_DELIVER], "worker-b", stale_after_seconds=60)
        assert [job["id"] for job in claimed] == [job_id]
        assert claimed[0]["attempts"] == 2
        assert (
            fail_job(
                job_id,
                "recovery failed",
                worker_id="worker-b",
                retry_delay_seconds=0,
            )
            is True
        )

        assert complete_job(job_id, worker_id="worker-a") is False
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, last_error FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_FAILED
        assert row["last_error"] == "recovery failed"

    def test_wrong_worker_cannot_complete_or_fail_while_locked(self, db):
        job_id = enqueue_job(JOB_DELIVER, {"user_id": "u1", "alert_id": "a1"})
        claim_jobs([JOB_DELIVER], "owner")

        assert complete_job(job_id, worker_id="intruder") is False
        assert (
            fail_job(job_id, "spoofed", worker_id="intruder", retry_delay_seconds=0)
            is False
        )

        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, locked_by, last_error FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_PROCESSING
        assert row["locked_by"] == "owner"
        assert row["last_error"] is None

        assert complete_job(job_id, worker_id="owner") is True
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_COMPLETED

    def test_late_fail_does_not_clobber_pending_retry_from_owner(self, db):
        """After reclaim fails into pending retry, original worker fail is ignored."""
        job_id = enqueue_job(
            JOB_DELIVER,
            {"user_id": "u1", "alert_id": "a1"},
            max_attempts=5,
        )
        claim_jobs([JOB_DELIVER], "worker-a")
        _stale_lock(job_id)

        claimed = claim_jobs([JOB_DELIVER], "worker-b", stale_after_seconds=60)
        assert [job["id"] for job in claimed] == [job_id]
        assert (
            fail_job(
                job_id,
                "transient from recovery",
                worker_id="worker-b",
                retry_delay_seconds=120,
            )
            is True
        )

        assert (
            fail_job(
                job_id,
                "late permanent from original",
                worker_id="worker-a",
                retry_delay_seconds=0,
            )
            is False
        )
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, last_error, locked_by FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        assert row["status"] == STATUS_PENDING
        assert row["last_error"] == "transient from recovery"
        assert row["locked_by"] is None

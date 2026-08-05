"""fail_job retry_delay must clamp so fromtimestamp cannot OverflowError."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.storage.alert_jobs import (
    JOB_EVALUATE_SYMBOL,
    MAX_RETRY_DELAY_SECONDS,
    STATUS_PENDING,
    claim_jobs,
    enqueue_job,
    fail_job,
)
from src.storage.database import get_connection, init_database


@pytest.fixture
def db(monkeypatch, tmp_path):
    db_path = tmp_path / "retry-delay.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def _claim_and_fail(job_id: int, retry_delay_seconds) -> None:
    claim_jobs([JOB_EVALUATE_SYMBOL], "worker-delay", limit=1)
    assert (
        fail_job(
            job_id,
            "transient",
            worker_id="worker-delay",
            retry_delay_seconds=retry_delay_seconds,
        )
        is True
    )


def test_fail_job_clamps_huge_retry_delay(db) -> None:
    """1e20 previously OverflowError'd datetime.fromtimestamp mid-fail path."""
    before = datetime.now(timezone.utc)
    job_id = enqueue_job(
        JOB_EVALUATE_SYMBOL,
        {"symbol": "AAPL"},
        max_attempts=3,
    )
    _claim_and_fail(job_id, 10**20)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT status, run_after FROM alert_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()

    assert row["status"] == STATUS_PENDING
    run_after = datetime.fromisoformat(row["run_after"])
    delta = (run_after - before).total_seconds()
    assert delta <= MAX_RETRY_DELAY_SECONDS + 5
    assert delta >= MAX_RETRY_DELAY_SECONDS - 5


def test_fail_job_clamps_negative_and_nonfinite_retry_delay(db) -> None:
    job_id = enqueue_job(
        JOB_EVALUATE_SYMBOL,
        {"symbol": "MSFT"},
        max_attempts=3,
    )
    before = datetime.now(timezone.utc)
    _claim_and_fail(job_id, float("inf"))

    with get_connection() as conn:
        row = conn.execute(
            "SELECT status, run_after FROM alert_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()

    assert row["status"] == STATUS_PENDING
    run_after = datetime.fromisoformat(row["run_after"])
    assert (run_after - before).total_seconds() < 5

    # Re-claim and fail with negative delay → immediate requeue.
    claim_jobs([JOB_EVALUATE_SYMBOL], "worker-delay", limit=1)
    before2 = datetime.now(timezone.utc)
    assert (
        fail_job(
            job_id,
            "again",
            worker_id="worker-delay",
            retry_delay_seconds=-100,
        )
        is True
    )
    with get_connection() as conn:
        row = conn.execute(
            "SELECT run_after FROM alert_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    run_after2 = datetime.fromisoformat(row["run_after"])
    assert (run_after2 - before2).total_seconds() < 5

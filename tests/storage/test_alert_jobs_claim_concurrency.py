"""Regression: concurrent claim_jobs must not double-claim the same pending row."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.storage.alert_jobs import (
    JOB_DELIVER,
    STATUS_PROCESSING,
    claim_jobs,
    enqueue_job,
)
from src.storage.database import get_connection, init_database


@pytest.fixture
def db(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs-claim-race.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def test_concurrent_claim_jobs_mutually_excludes_pending_row(db):
    """Two workers racing a single pending job → exactly one claim succeeds."""
    job_id = enqueue_job(JOB_DELIVER, {"user_id": "u1", "alert_id": "a1"})
    barrier = threading.Barrier(2)
    results: list[list[int]] = []
    lock = threading.Lock()

    def worker(worker_id: str) -> None:
        barrier.wait(timeout=5)
        claimed = claim_jobs([JOB_DELIVER], worker_id, limit=5)
        with lock:
            results.append([job["id"] for job in claimed])

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker, "worker-a"),
            pool.submit(worker, "worker-b"),
        ]
        for future in futures:
            future.result(timeout=10)

    claimed_ids = [job_id for batch in results for job_id in batch]
    assert sorted(claimed_ids) == [job_id]
    assert sum(1 for batch in results if batch) == 1

    with get_connection() as conn:
        row = conn.execute(
            "SELECT status, locked_by, attempts FROM alert_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    assert row["status"] == STATUS_PROCESSING
    assert row["locked_by"] in {"worker-a", "worker-b"}
    assert row["attempts"] == 1


def test_concurrent_claim_jobs_partitions_multiple_pending_rows(db):
    """Racing workers partition distinct pending jobs without overlap."""
    job_ids = {
        enqueue_job(JOB_DELIVER, {"user_id": "u1", "alert_id": f"a{i}"})
        for i in range(4)
    }
    barrier = threading.Barrier(2)
    results: list[set[int]] = []
    lock = threading.Lock()

    def worker(worker_id: str) -> None:
        barrier.wait(timeout=5)
        claimed = claim_jobs([JOB_DELIVER], worker_id, limit=10)
        with lock:
            results.append({job["id"] for job in claimed})

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker, "worker-a"),
            pool.submit(worker, "worker-b"),
        ]
        for future in futures:
            future.result(timeout=10)

    union = set().union(*results) if results else set()
    overlap = results[0] & results[1] if len(results) == 2 else set()
    assert union == job_ids
    assert overlap == set()
    assert sum(len(batch) for batch in results) == len(job_ids)

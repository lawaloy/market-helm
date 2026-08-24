"""A fresh processing lock must not be stolen by another worker's claim."""

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
    db_path = tmp_path / "jobs-fresh-lock.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def test_claim_does_not_steal_fresh_processing_lock(db) -> None:
    """Stale recovery uses locked_at <= now - timeout; a just-claimed row stays owned."""
    job_id = enqueue_job(JOB_DELIVER, {"user_id": "u1", "alert_id": "a1"})
    claimed_a = claim_jobs([JOB_DELIVER], "worker-a")
    assert [job["id"] for job in claimed_a] == [job_id]

    claimed_b = claim_jobs([JOB_DELIVER], "worker-b", stale_after_seconds=60)
    assert claimed_b == []

    with get_connection() as conn:
        row = conn.execute(
            "SELECT status, locked_by, attempts FROM alert_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    assert row["status"] == STATUS_PROCESSING
    assert row["locked_by"] == "worker-a"
    assert row["attempts"] == 1

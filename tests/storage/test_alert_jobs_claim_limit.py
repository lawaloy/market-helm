"""claim_jobs must not treat negative LIMIT as unlimited (SQLite quirk)."""

from __future__ import annotations

import pytest

from src.storage.alert_jobs import (
    JOB_EVALUATE_SYMBOL,
    STATUS_PENDING,
    claim_jobs,
    enqueue_job,
)
from src.storage.database import get_connection, init_database


@pytest.fixture
def db(monkeypatch, tmp_path):
    db_path = tmp_path / "claim-limit.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return db_path


def test_claim_jobs_negative_limit_claims_nothing(db) -> None:
    """SQLite LIMIT -1 means unlimited; a bad caller must not drain the queue."""
    for i in range(5):
        enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": f"T{i}"})

    claimed = claim_jobs([JOB_EVALUATE_SYMBOL], "worker-neg", limit=-1)
    assert claimed == []

    with get_connection() as conn:
        pending = conn.execute(
            "SELECT COUNT(*) AS n FROM alert_jobs WHERE status = ?",
            (STATUS_PENDING,),
        ).fetchone()["n"]
    assert pending == 5


def test_claim_jobs_zero_limit_claims_nothing(db) -> None:
    enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": "AAPL"})
    assert claim_jobs([JOB_EVALUATE_SYMBOL], "worker-zero", limit=0) == []

    with get_connection() as conn:
        pending = conn.execute(
            "SELECT COUNT(*) AS n FROM alert_jobs WHERE status = ?",
            (STATUS_PENDING,),
        ).fetchone()["n"]
    assert pending == 1


def test_claim_jobs_positive_limit_still_works(db) -> None:
    for i in range(3):
        enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": f"T{i}"})

    claimed = claim_jobs([JOB_EVALUATE_SYMBOL], "worker-pos", limit=2)
    assert len(claimed) == 2

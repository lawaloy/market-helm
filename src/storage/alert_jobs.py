"""Postgres-style job queue backed by SQLite (multi-user alert workers)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .database import get_connection

JOB_EVALUATE_SYMBOL = "evaluate_symbol"
JOB_DELIVER = "deliver"

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue_job(
    job_type: str,
    payload: Dict[str, Any],
    *,
    run_after: Optional[str] = None,
    max_attempts: int = 5,
) -> int:
    now = _utc_now()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO alert_jobs (
                job_type, payload_json, status, attempts, max_attempts,
                run_after, created_at, updated_at
            ) VALUES (?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (
                job_type,
                json.dumps(payload),
                STATUS_PENDING,
                max_attempts,
                run_after or now,
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)


def enqueue_jobs(job_type: str, payloads: List[Dict[str, Any]]) -> int:
    if not payloads:
        return 0
    now = _utc_now()
    rows = [
        (job_type, json.dumps(payload), STATUS_PENDING, 5, now, now, now)
        for payload in payloads
    ]
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO alert_jobs (
                job_type, payload_json, status, attempts, max_attempts,
                run_after, created_at, updated_at
            ) VALUES (?, ?, ?, 0, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def claim_jobs(
    job_types: List[str],
    worker_id: str,
    *,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    if not job_types:
        return []
    now = _utc_now()
    placeholders = ",".join("?" for _ in job_types)
    claimed: List[Dict[str, Any]] = []

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            f"""
            SELECT id FROM alert_jobs
            WHERE status = ? AND job_type IN ({placeholders}) AND run_after <= ?
            ORDER BY id
            LIMIT ?
            """,
            (STATUS_PENDING, *job_types, now, limit),
        ).fetchall()

        for row in rows:
            job_id = int(row["id"])
            updated = conn.execute(
                """
                UPDATE alert_jobs
                SET status = ?, locked_at = ?, locked_by = ?, updated_at = ?,
                    attempts = attempts + 1
                WHERE id = ? AND status = ?
                """,
                (STATUS_PROCESSING, now, worker_id, now, job_id, STATUS_PENDING),
            )
            if updated.rowcount != 1:
                continue
            job_row = conn.execute(
                "SELECT * FROM alert_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if job_row:
                claimed.append(_row_to_job(job_row))

    return claimed


def complete_job(job_id: int) -> None:
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE alert_jobs
            SET status = ?, updated_at = ?, locked_at = NULL, locked_by = NULL, last_error = NULL
            WHERE id = ?
            """,
            (STATUS_COMPLETED, now, job_id),
        )


def fail_job(job_id: int, error: str, *, retry_delay_seconds: int = 60) -> None:
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT attempts, max_attempts FROM alert_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if not row:
            return
        attempts = int(row["attempts"])
        max_attempts = int(row["max_attempts"])
        if attempts >= max_attempts:
            conn.execute(
                """
                UPDATE alert_jobs
                SET status = ?, last_error = ?, updated_at = ?, locked_at = NULL, locked_by = NULL
                WHERE id = ?
                """,
                (STATUS_FAILED, error[:500], now, job_id),
            )
            return
        run_after = datetime.fromtimestamp(
            now_dt.timestamp() + retry_delay_seconds,
            tz=timezone.utc,
        ).isoformat()
        conn.execute(
            """
            UPDATE alert_jobs
            SET status = ?, last_error = ?, updated_at = ?, run_after = ?,
                locked_at = NULL, locked_by = NULL
            WHERE id = ?
            """,
            (STATUS_PENDING, error[:500], now, run_after, job_id),
        )


def pending_job_count(job_types: Optional[List[str]] = None) -> int:
    now = _utc_now()
    with get_connection() as conn:
        if job_types:
            placeholders = ",".join("?" for _ in job_types)
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS n FROM alert_jobs
                WHERE status = ? AND run_after <= ? AND job_type IN ({placeholders})
                """,
                (STATUS_PENDING, now, *job_types),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM alert_jobs WHERE status = ? AND run_after <= ?",
                (STATUS_PENDING, now),
            ).fetchone()
    return int(row["n"])


def new_worker_id() -> str:
    return f"worker-{uuid.uuid4().hex[:12]}"


def _row_to_job(row: Any) -> Dict[str, Any]:
    return {
        "id": int(row["id"]),
        "job_type": row["job_type"],
        "payload": json.loads(row["payload_json"]),
        "status": row["status"],
        "attempts": int(row["attempts"]),
        "max_attempts": int(row["max_attempts"]),
    }

"""Database readiness and worker heartbeat persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .database import LATEST_SCHEMA_VERSION, get_connection


def database_health() -> Dict[str, Any]:
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        version = int(row["version"] or 0)
        return {"ok": version == LATEST_SCHEMA_VERSION, "schema_version": version,
                "expected_schema_version": LATEST_SCHEMA_VERSION}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def record_worker_heartbeat(worker_id: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(details or {}, separators=(",", ":"), default=str)
    with get_connection() as conn:
        updated = conn.execute(
            "UPDATE worker_heartbeats SET status = ?, last_seen_at = ?, details_json = ? WHERE worker_id = ?",
            (status, now, payload, worker_id),
        )
        if updated.rowcount == 0:
            conn.execute(
                "INSERT INTO worker_heartbeats (worker_id, status, last_seen_at, details_json) VALUES (?, ?, ?, ?)",
                (worker_id, status, now, payload),
            )


def latest_worker_heartbeat() -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT worker_id, status, last_seen_at, details_json FROM worker_heartbeats ORDER BY last_seen_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {"worker_id": row["worker_id"], "status": row["status"],
            "last_seen_at": row["last_seen_at"],
            "details": _heartbeat_details(row["details_json"])}


def _heartbeat_details(raw: Any) -> Dict[str, Any]:
    """Corrupt heartbeat JSON must not 500 readiness/worker probes."""
    try:
        details = json.loads(raw or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return details if isinstance(details, dict) else {}


def worker_health(*, stale_after_seconds: int) -> Dict[str, Any]:
    heartbeat = latest_worker_heartbeat()
    if not heartbeat:
        return {"ok": False, "reason": "no_heartbeat"}
    try:
        seen = datetime.fromisoformat(heartbeat["last_seen_at"])
        age = max(0.0, (datetime.now(timezone.utc) - seen).total_seconds())
    except (TypeError, ValueError):
        return {"ok": False, "reason": "invalid_heartbeat"}
    return {"ok": heartbeat["status"] == "healthy" and age <= stale_after_seconds,
            "age_seconds": round(age, 3), **heartbeat}

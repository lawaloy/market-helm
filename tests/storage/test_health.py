"""Hosted readiness probes must fail closed on missing/corrupt worker heartbeats."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.storage.database import LATEST_SCHEMA_VERSION, get_connection, init_database
from src.storage.health import (
    database_health,
    latest_worker_heartbeat,
    record_worker_heartbeat,
    worker_health,
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "health.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{path.as_posix()}")
    init_database()
    return path


def test_database_health_ok_on_current_schema(db):
    health = database_health()
    assert health["ok"] is True
    assert health["schema_version"] == LATEST_SCHEMA_VERSION
    assert health["expected_schema_version"] == LATEST_SCHEMA_VERSION


def test_database_health_not_ok_when_migrations_missing(db):
    with get_connection() as conn:
        conn.execute("DELETE FROM schema_migrations")
    health = database_health()
    assert health["ok"] is False
    assert health["schema_version"] == 0


def test_database_health_fail_closed_on_connection_error(db):
    with patch(
        "src.storage.health.get_connection",
        side_effect=RuntimeError("db down"),
    ):
        health = database_health()
    assert health == {"ok": False, "error": "RuntimeError"}


def test_worker_health_no_heartbeat(db):
    assert latest_worker_heartbeat() is None
    health = worker_health(stale_after_seconds=30)
    assert health == {"ok": False, "reason": "no_heartbeat"}


def test_record_heartbeat_upserts_same_worker(db):
    record_worker_heartbeat("w1", "running", {"tick": 1})
    record_worker_heartbeat("w1", "healthy", {"tick": 2})
    heartbeat = latest_worker_heartbeat()
    assert heartbeat is not None
    assert heartbeat["worker_id"] == "w1"
    assert heartbeat["status"] == "healthy"
    assert heartbeat["details"] == {"tick": 2}
    health = worker_health(stale_after_seconds=30)
    assert health["ok"] is True
    assert health["age_seconds"] >= 0


def test_worker_health_rejects_stale_heartbeat(db):
    record_worker_heartbeat("w1", "healthy")
    stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE worker_heartbeats SET last_seen_at = ? WHERE worker_id = ?",
            (stale, "w1"),
        )
    health = worker_health(stale_after_seconds=30)
    assert health["ok"] is False
    assert health["status"] == "healthy"
    assert health["age_seconds"] > 30


def test_worker_health_rejects_error_status_even_when_fresh(db):
    record_worker_heartbeat("w1", "error", {"error": "TimeoutError"})
    health = worker_health(stale_after_seconds=30)
    assert health["ok"] is False
    assert health["status"] == "error"
    assert health["details"] == {"error": "TimeoutError"}


def test_worker_health_invalid_timestamp(db):
    record_worker_heartbeat("w1", "healthy")
    with get_connection() as conn:
        conn.execute(
            "UPDATE worker_heartbeats SET last_seen_at = ? WHERE worker_id = ?",
            ("not-a-timestamp", "w1"),
        )
    assert worker_health(stale_after_seconds=30) == {
        "ok": False,
        "reason": "invalid_heartbeat",
    }


def test_corrupt_heartbeat_json_does_not_raise(db):
    record_worker_heartbeat("w1", "healthy", {"enqueued": 3})
    with get_connection() as conn:
        conn.execute(
            "UPDATE worker_heartbeats SET details_json = ? WHERE worker_id = ?",
            ("{not-json", "w1"),
        )
    heartbeat = latest_worker_heartbeat()
    assert heartbeat is not None
    assert heartbeat["details"] == {}
    health = worker_health(stale_after_seconds=30)
    assert health["ok"] is True
    assert health["details"] == {}


def test_non_object_heartbeat_json_is_dropped(db):
    record_worker_heartbeat("w1", "healthy")
    with get_connection() as conn:
        conn.execute(
            "UPDATE worker_heartbeats SET details_json = ? WHERE worker_id = ?",
            ("[1, 2]", "w1"),
        )
    assert latest_worker_heartbeat()["details"] == {}

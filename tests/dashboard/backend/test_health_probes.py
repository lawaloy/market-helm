"""/health/ready and /health/worker must 503 when hosted dependencies are unhealthy."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from dashboard.backend.main import app
from src.storage.database import init_database
from src.storage.health import record_worker_heartbeat


def test_ready_503_when_database_unhealthy(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL",
        f"sqlite:///{(tmp_path / 'ready.db').as_posix()}",
    )
    init_database()
    with patch(
        "src.storage.health.database_health",
        return_value={"ok": False, "schema_version": 0, "expected_schema_version": 5},
    ):
        response = TestClient(app).get("/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["database"]["ok"] is False
    assert payload["worker"] is None


def test_ready_reports_disabled_without_database(monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "disabled"}


def test_ready_stays_200_when_worker_heartbeat_lookup_fails(tmp_path, monkeypatch):
    """A worker-table error must not take down the hosted readiness probe."""
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL",
        f"sqlite:///{(tmp_path / 'ready-worker.db').as_posix()}",
    )
    init_database()
    with patch(
        "src.storage.health.latest_worker_heartbeat",
        side_effect=RuntimeError("heartbeat table missing"),
    ):
        response = TestClient(app).get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["database"]["ok"] is True
    assert payload["worker"] is None


def test_worker_probe_disabled_without_database(monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    response = TestClient(app).get("/health/worker")
    assert response.status_code == 200
    assert response.json() == {"status": "disabled"}


def test_worker_probe_503_without_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL",
        f"sqlite:///{(tmp_path / 'worker.db').as_posix()}",
    )
    init_database()
    response = TestClient(app).get("/health/worker")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unhealthy"
    assert payload["ok"] is False
    assert payload["reason"] == "no_heartbeat"


def test_worker_probe_200_when_heartbeat_is_fresh(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL",
        f"sqlite:///{(tmp_path / 'worker-ok.db').as_posix()}",
    )
    init_database()
    record_worker_heartbeat("probe-worker", "healthy", {"enqueued": 0})
    response = TestClient(app).get("/health/worker")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["ok"] is True
    assert payload["worker_id"] == "probe-worker"

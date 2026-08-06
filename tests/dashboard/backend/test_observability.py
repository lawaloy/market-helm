from fastapi.testclient import TestClient

from dashboard.backend.main import app


def test_liveness_readiness_and_metrics_file_mode(monkeypatch):
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    client = TestClient(app)
    live = client.get("/health/live", headers={"X-Request-ID": "probe-123"})
    assert live.status_code == 200
    assert live.headers["X-Request-ID"] == "probe-123"
    assert client.get("/health/ready").json()["status"] == "ready"
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "markethelm_http_requests_total" in metrics.text


def test_readiness_reports_database_schema(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{(tmp_path / 'health.db').as_posix()}")
    from src.storage.database import init_database, LATEST_SCHEMA_VERSION
    init_database()
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 200
    assert response.json()["database"]["schema_version"] == LATEST_SCHEMA_VERSION

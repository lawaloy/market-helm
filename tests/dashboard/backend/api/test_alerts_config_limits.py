"""PUT /api/alerts/config must reject oversized alerts arrays with HTTP 400."""

import pytest

from src.storage.alert_watches import MAX_ALERTS_PER_CONFIG


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from dashboard.backend.main import app

    return TestClient(app)


@pytest.fixture
def multi_user_env(tmp_path, monkeypatch):
    db_path = tmp_path / "config-limits.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "test-secret-min-16-chars")
    from src.storage.database import init_database

    init_database()


@pytest.fixture
def file_mode(tmp_path, monkeypatch):
    config_path = tmp_path / "alerts.json"
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    monkeypatch.setenv("MARKET_HELM_ALERTS_CONFIG", str(config_path))
    return config_path


def _register(client, email: str = "limits@example.com") -> str:
    r = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _payload(n: int) -> dict:
    return {
        "defaults": {},
        "alerts": [
            {
                "id": f"a{i}",
                "name": f"Alert {i}",
                "enabled": True,
                "cooldown_minutes": 15,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "less_than",
                    "value": 150,
                },
                "notifications": ["log"],
            }
            for i in range(n)
        ],
    }


def test_hosted_put_rejects_oversized_alerts_array(client, multi_user_env):
    token = _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(
        "/api/alerts/config",
        json=_payload(MAX_ALERTS_PER_CONFIG + 1),
        headers=headers,
    )

    assert response.status_code == 400
    assert "maximum" in response.json()["detail"].lower()

    saved = client.get("/api/alerts/config", headers=headers)
    assert saved.status_code == 200
    assert saved.json()["exists"] is False
    assert saved.json()["config"]["alerts"] == []


def test_hosted_put_accepts_exactly_max_alerts(client, multi_user_env):
    token = _register(client, "limits-max@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(
        "/api/alerts/config",
        json=_payload(MAX_ALERTS_PER_CONFIG),
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()["config"]["alerts"]) == MAX_ALERTS_PER_CONFIG


def test_file_put_rejects_oversized_alerts_array(client, file_mode):
    response = client.put(
        "/api/alerts/config",
        json=_payload(MAX_ALERTS_PER_CONFIG + 1),
    )

    assert response.status_code == 400
    assert "maximum" in response.json()["detail"].lower()
    assert not file_mode.exists()

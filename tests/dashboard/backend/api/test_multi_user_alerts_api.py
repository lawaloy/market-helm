"""Tests for per-user alerts API when MARKET_HELM_DATABASE_URL is set."""

import pytest


@pytest.fixture
def multi_user_env(tmp_path, monkeypatch):
    db_path = tmp_path / "markethelm.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "test-secret-min-16-chars")
    from src.storage.database import init_database

    init_database()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from dashboard.backend.main import app

    return TestClient(app)


def _register(client, email: str = "alerts@example.com") -> str:
    r = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


class TestMultiUserAlertsAPI:
    def test_config_requires_auth(self, client, multi_user_env):
        r = client.get("/api/alerts/config")
        assert r.status_code == 401

    def test_init_put_and_get_config(self, client, multi_user_env):
        token = _register(client)
        headers = {"Authorization": f"Bearer {token}"}

        r = client.post("/api/alerts/init", headers=headers)
        assert r.status_code == 200

        payload = {
            "defaults": {"email_to": "user@example.com"},
            "alerts": [
                {
                    "id": "watch_aapl",
                    "name": "AAPL watch",
                    "enabled": True,
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": "below",
                        "value": 100,
                    },
                }
            ],
        }
        r2 = client.put("/api/alerts/config", json=payload, headers=headers)
        assert r2.status_code == 200
        assert r2.json()["exists"] is True
        assert r2.json()["config"]["defaults"]["email_to"] == "user@example.com"

        r3 = client.get("/api/alerts/config", headers=headers)
        assert r3.status_code == 200
        assert len(r3.json()["config"]["alerts"]) == 1

    def test_invalid_price_rule_is_rejected_without_persisting(self, client, multi_user_env):
        token = _register(client)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "defaults": {"email_to": "user@example.com"},
            "alerts": [
                {
                    "id": "bad-price",
                    "enabled": True,
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": "below",
                        "value": "not-a-number",
                    },
                }
            ],
        }

        response = client.put("/api/alerts/config", json=payload, headers=headers)

        assert response.status_code == 400
        assert "invalid price threshold" in response.json()["detail"]
        saved = client.get("/api/alerts/config", headers=headers)
        assert saved.status_code == 200
        assert saved.json()["exists"] is False
        assert saved.json()["config"]["alerts"] == []

    def test_users_have_isolated_configs(self, client, multi_user_env):
        token_a = _register(client, "a@example.com")
        token_b = _register(client, "b@example.com")

        client.post("/api/alerts/init", headers={"Authorization": f"Bearer {token_a}"})
        client.post("/api/alerts/init", headers={"Authorization": f"Bearer {token_b}"})

        client.put(
            "/api/alerts/config",
            json={"defaults": {"email_to": "a@example.com"}, "alerts": []},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        client.put(
            "/api/alerts/config",
            json={"defaults": {"email_to": "b@example.com"}, "alerts": []},
            headers={"Authorization": f"Bearer {token_b}"},
        )

        cfg_a = client.get("/api/alerts/config", headers={"Authorization": f"Bearer {token_a}"}).json()
        cfg_b = client.get("/api/alerts/config", headers={"Authorization": f"Bearer {token_b}"}).json()
        assert cfg_a["config"]["defaults"]["email_to"] == "a@example.com"
        assert cfg_b["config"]["defaults"]["email_to"] == "b@example.com"

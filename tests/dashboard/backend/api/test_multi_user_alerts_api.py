"""Tests for per-user alerts API when MARKET_HELM_DATABASE_URL is set."""

import json

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

    def test_webhook_secret_is_user_scoped_and_write_only(
        self, client, multi_user_env, tmp_path, monkeypatch
    ):
        from src.storage.user_alerts import load_user_alerts_config
        from src.storage.users import get_user_by_email

        user_config_dir = tmp_path / "user-config"
        monkeypatch.setattr("src.alerts.alert_paths.user_config_dir", lambda: user_config_dir)
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/global/token")

        token = _register(client, "webhook@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        client.post("/api/alerts/init", headers=headers)

        payload = {
            "defaults": {
                "webhook_url": "https://discord.com/api/webhooks/user/token",
                "webhook_format": "discord",
                "notify_webhook": True,
            },
            "alerts": [
                {
                    "id": "aapl_drop",
                    "enabled": True,
                    "condition": {
                        "type": "price_threshold",
                        "symbol": "AAPL",
                        "operator": "less_than",
                        "value": 150,
                    },
                    "notifications": ["webhook"],
                }
            ],
        }

        first = client.put("/api/alerts/config", json=payload, headers=headers)

        assert first.status_code == 200
        assert first.json()["channels"]["webhook_url"] is True
        serialized = json.dumps(first.json())
        assert "user/token" not in serialized
        assert "global/token" not in serialized
        assert not (user_config_dir / ".env").exists()

        # The frontend sends later edits without the write-only URL; keep the
        # saved per-user secret instead of falling back to the global env var.
        payload["defaults"].pop("webhook_url")
        payload["defaults"]["email_to"] = "webhook@example.com"
        second = client.put("/api/alerts/config", json=payload, headers=headers)

        assert second.status_code == 200
        assert second.json()["channels"]["webhook_url"] is True
        assert "user/token" not in json.dumps(second.json())
        assert second.json()["config"]["alerts"][0]["id"] == "aapl_drop"

        saved_user = get_user_by_email("webhook@example.com")
        assert saved_user is not None
        _, raw = load_user_alerts_config(saved_user["id"])
        assert raw is not None
        assert raw["defaults"]["webhook_url"].endswith("/user/token")

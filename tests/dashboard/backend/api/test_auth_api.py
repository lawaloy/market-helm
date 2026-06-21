"""Tests for multi-user auth API."""

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


class TestAuthAPI:
    def test_register_disabled_without_database(self, client, monkeypatch):
        monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
        r = client.post(
            "/api/auth/register",
            json={"email": "a@example.com", "password": "password123"},
        )
        assert r.status_code == 501

    def test_register_login_and_me(self, client, multi_user_env):
        r = client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "password123"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["token_type"] == "bearer"
        assert data["access_token"]
        assert data["user"]["email"] == "user@example.com"

        r2 = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        )
        assert r2.status_code == 200
        token = r2.json()["access_token"]

        r3 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r3.status_code == 200
        assert r3.json()["email"] == "user@example.com"

    def test_login_invalid_credentials(self, client, multi_user_env):
        client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "password123"},
        )
        r = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "wrongpassword"},
        )
        assert r.status_code == 401

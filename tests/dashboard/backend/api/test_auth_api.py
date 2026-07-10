"""Tests for multi-user auth API."""

import pytest
from src.storage.session import create_access_token


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

    def test_register_duplicate_email_returns_400(self, client, multi_user_env):
        payload = {"email": "User@Example.com", "password": "password123"}
        first = client.post("/api/auth/register", json=payload)
        assert first.status_code == 200

        duplicate = client.post(
            "/api/auth/register",
            json={"email": " user@example.com ", "password": "password123"},
        )

        assert duplicate.status_code == 400
        assert "already exists" in duplicate.json()["detail"]

    @pytest.mark.parametrize(
        "authorization",
        [
            None,
            "Token abc",
            "Bearer",
            "Bearer not-a-valid-token",
        ],
    )
    def test_me_rejects_missing_or_invalid_bearer_token(
        self,
        client,
        multi_user_env,
        authorization,
    ):
        headers = {}
        if authorization is not None:
            headers["Authorization"] = authorization

        r = client.get("/api/auth/me", headers=headers)

        assert r.status_code == 401
        assert r.json()["detail"] == "Authentication required."

    def test_me_rejects_expired_token(self, client, multi_user_env):
        token = create_access_token("missing-user", ttl_seconds=-1)

        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert r.status_code == 401
        assert r.json()["detail"] == "Authentication required."

    def test_me_rejects_token_for_deleted_user(self, client, multi_user_env):
        registered = client.post(
            "/api/auth/register",
            json={"email": "deleted@example.com", "password": "password123"},
        )
        assert registered.status_code == 200
        user_id = registered.json()["user"]["id"]
        token = registered.json()["access_token"]

        from src.storage.database import get_connection

        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert r.status_code == 401
        assert r.json()["detail"] == "User not found."

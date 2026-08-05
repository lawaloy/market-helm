"""API register/login must reject oversized passwords before scrypt."""

import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from dashboard.backend.main import app

    return TestClient(app)


@pytest.fixture
def multi_user_env(tmp_path, monkeypatch):
    db_path = tmp_path / "password-api.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "test-secret-min-16-chars")
    from src.storage.database import init_database

    init_database()


def test_register_rejects_oversized_password(client, multi_user_env):
    from src.storage.users import MAX_PASSWORD_LENGTH

    response = client.post(
        "/api/auth/register",
        json={
            "email": "toolong@example.com",
            "password": "x" * (MAX_PASSWORD_LENGTH + 1),
        },
    )
    assert response.status_code == 422


def test_login_rejects_oversized_password(client, multi_user_env):
    from src.storage.users import MAX_PASSWORD_LENGTH

    ok = client.post(
        "/api/auth/register",
        json={"email": "ok@example.com", "password": "password123"},
    )
    assert ok.status_code == 200

    response = client.post(
        "/api/auth/login",
        json={
            "email": "ok@example.com",
            "password": "x" * (MAX_PASSWORD_LENGTH + 1),
        },
    )
    assert response.status_code == 422

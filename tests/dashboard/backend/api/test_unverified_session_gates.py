"""Unverified sessions must not reach hosted tenant or expensive routes."""

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL",
        f"sqlite:///{(tmp_path / 'unverified.db').as_posix()}",
    )
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "test-secret-min-16-chars")
    monkeypatch.setenv("MARKET_HELM_REQUIRE_EMAIL_VERIFICATION", "true")
    monkeypatch.setenv("MARKET_HELM_PUBLIC_URL", "https://staging.example.com")
    from src.storage.database import init_database

    init_database()
    from fastapi.testclient import TestClient
    from dashboard.backend.main import app

    return TestClient(app)


def test_unverified_registration_token_is_forbidden_until_confirm(client, monkeypatch):
    sent = {}
    monkeypatch.setattr(
        "dashboard.backend.api.auth.send_account_email",
        lambda **kwargs: sent.update(kwargs) is None or True,
    )
    registered = client.post(
        "/api/auth/register",
        json={"email": "gated@example.com", "password": "password123"},
    )
    assert registered.status_code == 200
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 403
    assert me.json()["detail"] == "Email verification required."

    alerts = client.get("/api/alerts/config", headers=headers)
    assert alerts.status_code == 403
    assert alerts.json()["detail"] == "Email verification required."

    data_info = client.get("/api/data-info", headers=headers)
    assert data_info.status_code == 403
    assert data_info.json()["detail"] == "Email verification required."

    refresh = client.post("/api/refresh", headers=headers)
    assert refresh.status_code == 403
    assert refresh.json()["detail"] == "Email verification required."

    changed = client.post(
        "/api/auth/password/change",
        headers=headers,
        json={"current_password": "password123", "new_password": "new-password-123"},
    )
    assert changed.status_code == 403
    assert changed.json()["detail"] == "Email verification required."

    login = client.post(
        "/api/auth/login",
        json={"email": "gated@example.com", "password": "password123"},
    )
    assert login.status_code == 403
    assert login.json()["detail"] == "Verify your email before signing in."

    confirmed = client.post(
        "/api/auth/verify-email/confirm", json={"token": sent["token"]}
    )
    assert confirmed.status_code == 200

    # Confirming email does not revoke the registration token.
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.get("/api/alerts/config", headers=headers).status_code == 200
    assert client.post(
        "/api/auth/login",
        json={"email": "gated@example.com", "password": "password123"},
    ).status_code == 200

"""Password change and HTTP account delete must revoke expensive hosted routes."""

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MARKET_HELM_DATABASE_URL",
        f"sqlite:///{(tmp_path / 'session-expensive.db').as_posix()}",
    )
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "test-secret-min-16-chars")
    from src.storage.database import init_database

    init_database()
    from fastapi.testclient import TestClient
    from dashboard.backend.main import app

    return TestClient(app)


def _register(client, email: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _assert_expensive_routes_401(client, headers: dict, detail: str) -> None:
    run = client.post("/api/alerts/run", headers=headers)
    assert run.status_code == 401
    assert run.json()["detail"] == detail

    test = client.post(
        "/api/alerts/test",
        json={"id": "any", "dry_run": True},
        headers=headers,
    )
    assert test.status_code == 401
    assert test.json()["detail"] == detail

    refresh = client.post("/api/refresh", headers=headers)
    assert refresh.status_code == 401
    assert refresh.json()["detail"] == detail


def _assert_expensive_routes_authorized(client, headers: dict) -> None:
    run = client.post("/api/alerts/run", headers=headers)
    assert run.status_code == 200
    assert run.json()["triggered"] == 0
    assert run.json()["message"] == "No active watches configured."

    test = client.post(
        "/api/alerts/test",
        json={"id": "any", "dry_run": True},
        headers=headers,
    )
    assert test.status_code == 404
    assert test.json()["detail"] == "No alerts config for this user."

    refresh = client.post("/api/refresh", headers=headers)
    assert refresh.status_code == 200


def test_change_password_revokes_old_token_on_run_test_and_refresh(client) -> None:
    token_a = _register(client, "revoke-run-a@example.com")
    token_b = _register(client, "revoke-run-b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    changed = client.post(
        "/api/auth/password/change",
        headers=headers_a,
        json={"current_password": "password123", "new_password": "new-password-123"},
    )
    assert changed.status_code == 200

    _assert_expensive_routes_401(client, headers_a, "Session revoked.")
    _assert_expensive_routes_authorized(client, headers_b)


def test_http_delete_account_rejects_old_token_on_run_test_and_refresh(client) -> None:
    token_a = _register(client, "delete-run-a@example.com")
    token_b = _register(client, "delete-run-b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    deleted = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers_a,
        json={"current_password": "password123", "confirmation": "DELETE"},
    )
    assert deleted.status_code == 200

    _assert_expensive_routes_401(client, headers_a, "User not found.")
    _assert_expensive_routes_authorized(client, headers_b)

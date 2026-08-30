"""Hosted GET must not 500 when stored config_json has a non-list alerts key."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def multi_user_env(tmp_path, monkeypatch):
    db_path = tmp_path / "hosted-nonlist.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "test-secret-min-16-chars")
    from src.storage.database import init_database

    init_database()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from dashboard.backend.main import app

    return TestClient(app)


def _register(client, email: str) -> tuple[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    return body["access_token"], body["user"]["id"]


def _price_payload(alert_id: str, symbol: str = "AAPL") -> dict:
    return {
        "defaults": {"email_to": f"{alert_id}@example.com"},
        "alerts": [
            {
                "id": alert_id,
                "name": alert_id,
                "enabled": True,
                "condition": {
                    "type": "price_threshold",
                    "symbol": symbol,
                    "operator": "less_than",
                    "value": 100,
                },
                "notifications": ["log"],
            }
        ],
    }


@pytest.mark.parametrize("bad_alerts", [1, True, {"id": "x"}])
def test_hosted_get_config_soft_fails_non_list_alerts_without_touching_sibling(
    client, multi_user_env, bad_alerts
) -> None:
    """Settings GET polishes stored JSON before normalize; ``alerts: 1`` 500ed."""
    token_a, user_a = _register(
        client, f"nonlist-a-{type(bad_alerts).__name__}@example.com"
    )
    token_b, _user_b = _register(
        client, f"nonlist-b-{type(bad_alerts).__name__}@example.com"
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    saved = client.put(
        "/api/alerts/config",
        headers=headers_b,
        json=_price_payload("sibling-msft", "MSFT"),
    )
    assert saved.status_code == 200

    from src.storage.database import get_connection

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_alert_configs (user_id, config_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (
                user_a,
                json.dumps({"defaults": {}, "alerts": bad_alerts}),
                "2026-07-24T00:00:00+00:00",
            ),
        )

    poisoned = client.get("/api/alerts/config", headers=headers_a)
    sibling = client.get("/api/alerts/config", headers=headers_b)

    assert poisoned.status_code == 200
    assert poisoned.json()["exists"] is True
    assert poisoned.json()["config"]["alerts"] == []
    assert sibling.status_code == 200
    assert [alert["id"] for alert in sibling.json()["config"]["alerts"]] == [
        "sibling-msft"
    ]

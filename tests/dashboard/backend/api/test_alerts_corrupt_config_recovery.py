"""Hosted init/PUT must recover a poison config row without touching sibling tenants."""

import pytest

from src.storage.alert_watches import list_watches_for_symbol
from src.storage.database import get_connection


@pytest.fixture
def multi_user_env(tmp_path, monkeypatch):
    db_path = tmp_path / "corrupt-recover.db"
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


def _price_payload(alert_id: str, symbol: str) -> dict:
    return {
        "defaults": {},
        "alerts": [
            {
                "id": alert_id,
                "name": alert_id,
                "enabled": True,
                "condition": {
                    "type": "price_threshold",
                    "symbol": symbol,
                    "operator": "less_than",
                    "value": 150,
                },
                "notifications": ["log"],
            }
        ],
    }


def _poison_row(user_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_alert_configs (user_id, config_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (user_id, "{not-json", "2026-07-24T00:00:00+00:00"),
        )


def test_hosted_init_409s_on_corrupt_row_until_force_without_touching_sibling(
    client, multi_user_env
) -> None:
    token_a, user_a = _register(client, "init-corrupt-a@example.com")
    token_b, user_b = _register(client, "init-corrupt-b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    sibling = client.put(
        "/api/alerts/config",
        headers=headers_b,
        json=_price_payload("sibling-msft", "MSFT"),
    )
    assert sibling.status_code == 200
    _poison_row(user_a)

    conflict = client.post("/api/alerts/init", headers=headers_a)
    assert conflict.status_code == 409
    assert "force=true" in conflict.json()["detail"]

    still_poisoned = client.get("/api/alerts/config", headers=headers_a)
    assert still_poisoned.status_code == 200
    assert still_poisoned.json()["exists"] is True
    assert still_poisoned.json()["config"]["alerts"] == []

    forced = client.post("/api/alerts/init?force=true", headers=headers_a)
    assert forced.status_code == 200
    recovered = client.get("/api/alerts/config", headers=headers_a)
    assert recovered.status_code == 200
    assert recovered.json()["exists"] is True
    assert recovered.json()["config"]["alerts"] == []

    sibling_cfg = client.get("/api/alerts/config", headers=headers_b)
    assert sibling_cfg.status_code == 200
    assert [alert["id"] for alert in sibling_cfg.json()["config"]["alerts"]] == [
        "sibling-msft"
    ]
    assert {(w["user_id"], w["alert_id"]) for w in list_watches_for_symbol("MSFT")} == {
        (user_b, "sibling-msft")
    }
    assert list_watches_for_symbol("AAPL") == []


def test_hosted_put_replaces_corrupt_row_and_reindexes_watches_without_touching_sibling(
    client, multi_user_env
) -> None:
    token_a, user_a = _register(client, "put-corrupt-a@example.com")
    token_b, user_b = _register(client, "put-corrupt-b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    sibling = client.put(
        "/api/alerts/config",
        headers=headers_b,
        json=_price_payload("sibling-msft", "MSFT"),
    )
    assert sibling.status_code == 200
    _poison_row(user_a)

    saved = client.put(
        "/api/alerts/config",
        headers=headers_a,
        json=_price_payload("aapl_drop", "AAPL"),
    )
    assert saved.status_code == 200
    assert [alert["id"] for alert in saved.json()["config"]["alerts"]] == ["aapl_drop"]

    got_a = client.get("/api/alerts/config", headers=headers_a)
    got_b = client.get("/api/alerts/config", headers=headers_b)
    assert got_a.status_code == 200
    assert [alert["id"] for alert in got_a.json()["config"]["alerts"]] == ["aapl_drop"]
    assert got_b.status_code == 200
    assert [alert["id"] for alert in got_b.json()["config"]["alerts"]] == [
        "sibling-msft"
    ]

    aapl = {(w["user_id"], w["alert_id"]) for w in list_watches_for_symbol("AAPL")}
    assert aapl == {(user_a, "aapl_drop")}
    assert [w["alert_id"] for w in list_watches_for_symbol("MSFT")] == ["sibling-msft"]
    assert {w["user_id"] for w in list_watches_for_symbol("MSFT")} == {user_b}

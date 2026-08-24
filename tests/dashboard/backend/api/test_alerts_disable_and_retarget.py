"""Hosted Settings disable/retarget must drop the old watch index key."""

import pytest

from src.storage.alert_watches import list_enabled_symbols, list_watches_for_symbol
from src.storage.database import get_connection


@pytest.fixture
def multi_user_env(tmp_path, monkeypatch):
    db_path = tmp_path / "disable-retarget.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("MARKET_HELM_AUTH_SECRET", "test-secret-min-16-chars")
    from src.storage.database import init_database

    init_database()


@pytest.fixture
def client(multi_user_env):
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


def _price_payload(alert_id: str, symbol: str, *, enabled: bool = True) -> dict:
    return {
        "defaults": {},
        "alerts": [
            {
                "id": alert_id,
                "name": alert_id,
                "enabled": enabled,
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


def _watch_ids(symbol: str) -> set[tuple[str, str]]:
    return {(w["user_id"], w["alert_id"]) for w in list_watches_for_symbol(symbol)}


def _enabled_flag(user_id: str, alert_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT enabled FROM alert_watches WHERE user_id = ? AND alert_id = ?",
            (user_id, alert_id),
        ).fetchone()
    assert row is not None
    return int(row["enabled"])


def test_put_disable_drops_watch_from_index_without_touching_sibling(client) -> None:
    token_a, user_a = _register(client, "disable-a@example.com")
    token_b, user_b = _register(client, "disable-b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    saved_a = client.put(
        "/api/alerts/config",
        headers=headers_a,
        json=_price_payload("aapl_drop", "AAPL"),
    )
    saved_b = client.put(
        "/api/alerts/config",
        headers=headers_b,
        json=_price_payload("sibling-msft", "MSFT"),
    )
    assert saved_a.status_code == 200
    assert saved_b.status_code == 200
    assert _watch_ids("AAPL") == {(user_a, "aapl_drop")}
    assert _watch_ids("MSFT") == {(user_b, "sibling-msft")}
    assert _enabled_flag(user_a, "aapl_drop") == 1

    disabled = client.put(
        "/api/alerts/config",
        headers=headers_a,
        json=_price_payload("aapl_drop", "AAPL", enabled=False),
    )
    assert disabled.status_code == 200
    assert disabled.json()["config"]["alerts"][0]["enabled"] is False
    assert disabled.json()["config"]["alerts"][0]["id"] == "aapl_drop"

    status = client.get("/api/alerts/status", headers=headers_a)
    assert status.status_code == 200
    assert status.json()["active_watches"] == 0

    assert _watch_ids("AAPL") == set()
    assert "AAPL" not in list_enabled_symbols()
    assert _enabled_flag(user_a, "aapl_drop") == 0
    assert _watch_ids("MSFT") == {(user_b, "sibling-msft")}
    assert list_enabled_symbols() == ["MSFT"]

    sibling = client.get("/api/alerts/config", headers=headers_b)
    assert sibling.status_code == 200
    assert [alert["id"] for alert in sibling.json()["config"]["alerts"]] == [
        "sibling-msft"
    ]
    assert sibling.json()["config"]["alerts"][0]["enabled"] is True


def test_put_same_id_symbol_swap_drops_old_symbol_without_touching_sibling(
    client,
) -> None:
    token_a, user_a = _register(client, "retarget-a@example.com")
    token_b, user_b = _register(client, "retarget-b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    saved_a = client.put(
        "/api/alerts/config",
        headers=headers_a,
        json=_price_payload("price_watch", "AAPL"),
    )
    saved_b = client.put(
        "/api/alerts/config",
        headers=headers_b,
        json=_price_payload("sibling-msft", "MSFT"),
    )
    assert saved_a.status_code == 200
    assert saved_b.status_code == 200
    assert _watch_ids("AAPL") == {(user_a, "price_watch")}
    assert _watch_ids("MSFT") == {(user_b, "sibling-msft")}

    swapped = client.put(
        "/api/alerts/config",
        headers=headers_a,
        json=_price_payload("price_watch", "GOOG"),
    )
    assert swapped.status_code == 200
    assert [alert["id"] for alert in swapped.json()["config"]["alerts"]] == [
        "price_watch"
    ]
    assert swapped.json()["config"]["alerts"][0]["condition"]["symbol"] == "GOOG"

    assert _watch_ids("AAPL") == set()
    assert "AAPL" not in list_enabled_symbols()
    assert _watch_ids("GOOG") == {(user_a, "price_watch")}
    assert _watch_ids("MSFT") == {(user_b, "sibling-msft")}
    assert list_enabled_symbols() == ["GOOG", "MSFT"]

    sibling = client.get("/api/alerts/config", headers=headers_b)
    assert sibling.status_code == 200
    assert [alert["id"] for alert in sibling.json()["config"]["alerts"]] == [
        "sibling-msft"
    ]

"""Hosted notification-channel PUTs must take effect for already-queued deliver jobs.

Cooldown (#457) is a dedicated watch column. Channel membership lives in
``alert_json`` / defaults and is re-read at deliver time. Turning webhook off
after a job is already queued must not POST, while a sibling tenant still
notifies.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.alerts.job_processor import process_job_queue
from src.storage.alert_jobs import JOB_DELIVER, enqueue_job, pending_job_count
from src.storage.alert_watches import get_watch


@pytest.fixture
def multi_user_env(tmp_path, monkeypatch):
    db_path = tmp_path / "notifications-queued.db"
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


def _webhook_payload(
    alert_id: str,
    symbol: str,
    webhook_url: str,
    *,
    notifications: list[str],
) -> dict:
    return {
        "defaults": {
            "webhook_url": webhook_url,
            "webhook_format": "json",
        },
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
                "notifications": notifications,
            }
        ],
    }


def _deliver_job(user_id: str, alert_id: str, symbol: str, event_ts: str) -> dict:
    return {
        "user_id": user_id,
        "alert_id": alert_id,
        "event": {
            "alert_id": alert_id,
            "alert_name": alert_id,
            "symbols": [symbol],
            "timestamp": event_ts,
            "condition_type": "price_threshold",
            "user_id": user_id,
        },
    }


def test_put_drops_webhook_skips_queued_deliver_without_touching_sibling(client) -> None:
    token_a, user_a = _register(client, "notify-deliver-a@example.com")
    token_b, user_b = _register(client, "notify-deliver-b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    url_a = "https://hooks.example/tenant-a"
    url_b = "https://hooks.example/tenant-b"

    saved_a = client.put(
        "/api/alerts/config",
        headers=headers_a,
        json=_webhook_payload("aapl_drop", "AAPL", url_a, notifications=["log", "webhook"]),
    )
    saved_b = client.put(
        "/api/alerts/config",
        headers=headers_b,
        json=_webhook_payload("sibling-msft", "MSFT", url_b, notifications=["webhook"]),
    )
    assert saved_a.status_code == 200
    assert saved_b.status_code == 200
    assert get_watch(user_a, "aapl_drop")["alert"]["notifications"] == ["log", "webhook"]
    assert get_watch(user_a, "aapl_drop")["defaults"]["webhook_url"] == url_a

    event_ts = datetime.now(timezone.utc).isoformat()
    enqueue_job(JOB_DELIVER, _deliver_job(user_a, "aapl_drop", "AAPL", event_ts))
    enqueue_job(JOB_DELIVER, _deliver_job(user_b, "sibling-msft", "MSFT", event_ts))

    silenced = client.put(
        "/api/alerts/config",
        headers=headers_a,
        json=_webhook_payload("aapl_drop", "AAPL", url_a, notifications=["log"]),
    )
    assert silenced.status_code == 200
    assert get_watch(user_a, "aapl_drop")["alert"]["notifications"] == ["log"]
    assert get_watch(user_a, "aapl_drop")["defaults"]["webhook_url"] == url_a
    assert get_watch(user_b, "sibling-msft")["alert"]["notifications"] == ["webhook"]

    with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True) as send_log:
        with patch("src.alerts.notifiers.webhook_notifier.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            stats = process_job_queue("notify-deliver-worker")

    assert stats["evaluated"] == 0
    assert stats["delivered"] == 2
    assert stats["failed"] == 0
    assert pending_job_count([JOB_DELIVER]) == 0
    send_log.assert_called_once()
    log_event = send_log.call_args.args[0]
    assert log_event["alert_id"] == "aapl_drop"
    assert log_event["user_id"] == user_a
    mock_post.assert_called_once()
    assert mock_post.call_args.args[0] == url_b

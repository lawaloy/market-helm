"""Hosted Check watches now must evaluate screening_match rules.

Scheduled orchestration is symbol-centric (price watches only). Manual
``run_user_check`` still walks ``AlertEngine.evaluate`` over the market
snapshot, so a screening-only tenant can fire on saved/live rows without
being enqueued as ``evaluate_symbol`` jobs. Existing worker tests only
assert that screening rules are omitted from the live-quote symbol list.
"""

from unittest.mock import patch

import pytest

from src.alerts import alert_worker
from src.alerts.alert_orchestrator import run_orchestrator_tick
from src.storage.alert_jobs import JOB_EVALUATE_SYMBOL, pending_job_count
from src.storage.alert_watches import get_watch, list_enabled_symbols
from src.storage.database import get_connection, init_database
from src.storage.user_alerts import save_user_alerts_config
from src.storage.users import create_user


@pytest.fixture
def db_users(tmp_path, monkeypatch):
    db_path = tmp_path / "screening-check.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return (
        create_user("screen-a@example.com", "password123")["id"],
        create_user("screen-b@example.com", "password123")["id"],
    )


def _screening_config(alert_id: str = "volume-spike") -> dict:
    return {
        "defaults": {},
        "alerts": [
            {
                "id": alert_id,
                "name": "Volume spike",
                "enabled": True,
                "cooldown_minutes": 0,
                "condition": {
                    "type": "screening_match",
                    "filters": {"volume_threshold": 1_000_000},
                },
                "notifications": ["log"],
            }
        ],
    }


def test_run_user_check_delivers_screening_match_and_stays_tenant_scoped(
    db_users,
) -> None:
    """Manual hosted checks must fire screening rules without touching siblings."""
    user_a, user_b = db_users
    save_user_alerts_config(user_a, _screening_config("volume-a"))
    save_user_alerts_config(user_b, _screening_config("volume-b"))

    watch = get_watch(user_a, "volume-a")
    assert watch is not None
    assert watch["alert"]["condition"]["type"] == "screening_match"
    assert list_enabled_symbols() == []

    stocks = [
        {
            "symbol": "AAPL",
            "volume": 2_000_000,
            "change_percent": 2.0,
            "close": 150.0,
        },
        {
            "symbol": "MSFT",
            "volume": 100_000,
            "change_percent": 0.5,
            "close": 400.0,
        },
    ]

    with patch(
        "src.alerts.market_snapshot.load_market_snapshot",
        return_value=("2026-06-09", {"AAPL": 150.0}, stocks),
    ) as load_snapshot:
        with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True) as send:
            with patch("src.alerts.alert_worker.run_db_worker_cycle") as mock_cycle:
                result = alert_worker.run_user_check(user_a)

    assert result["triggered"] == 1
    assert result["last_data_date"] == "2026-06-09"
    assert result["message"] is None
    event = result["events"][0]
    assert event["condition_type"] == "screening_match"
    assert event["symbols"] == ["AAPL"]
    assert event["alert_id"] == "volume-a"
    assert send.call_count == 1
    mock_cycle.assert_not_called()
    # Screening is not a price watch — no live-quote symbol list.
    load_snapshot.assert_called_once_with([], fetch_missing_quotes=True)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT user_id, alert_id FROM alert_trigger_state ORDER BY alert_id"
        ).fetchall()
    assert [(row["user_id"], row["alert_id"]) for row in rows] == [
        (user_a, "volume-a"),
    ]


def test_screening_only_tenant_does_not_enqueue_scheduled_jobs(db_users) -> None:
    """Enabled screening watches persist but never enter the symbol job queue."""
    user_a, _user_b = db_users
    save_user_alerts_config(user_a, _screening_config())

    assert get_watch(user_a, "volume-spike") is not None
    assert list_enabled_symbols() == []

    with patch("src.alerts.alert_orchestrator.load_market_snapshot") as mock_snapshot:
        tick = run_orchestrator_tick()

    mock_snapshot.assert_not_called()
    assert tick["enqueued"] == 0
    assert "No enabled watches" in (tick["message"] or "")
    assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 0

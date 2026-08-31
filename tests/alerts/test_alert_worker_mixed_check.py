"""Hosted Check watches now must fire screening and price watches together.

Settings can mix ``screening_match`` with ``price_threshold``. ``run_user_check``
requests live quotes only for price symbols, then ``AlertEngine.evaluate`` walks
the full snapshot — screening must still match rows that are not in the price
watch list. Existing worker tests only assert the quote-fetch symbol list when
the snapshot is empty, so they cannot catch a regression that later filters
``stocks`` down to those symbols. The scheduled orchestrator stays
symbol-centric and must enqueue only the price watch.
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
    db_path = tmp_path / "mixed-check.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return (
        create_user("mixed-a@example.com", "password123")["id"],
        create_user("mixed-b@example.com", "password123")["id"],
    )


def _mixed_config(price_id: str = "aapl-low", screen_id: str = "volume-spike") -> dict:
    return {
        "defaults": {},
        "alerts": [
            {
                "id": price_id,
                "name": "AAPL Drop",
                "enabled": True,
                "cooldown_minutes": 0,
                "condition": {
                    "type": "price_threshold",
                    "symbol": "AAPL",
                    "operator": "less_than",
                    "value": 200,
                },
                "notifications": ["log"],
            },
            {
                "id": screen_id,
                "name": "Volume spike",
                "enabled": True,
                "cooldown_minutes": 0,
                "condition": {
                    "type": "screening_match",
                    "filters": {"volume_threshold": 1_000_000},
                },
                "notifications": ["log"],
            },
        ],
    }


def _mixed_snapshot_stocks() -> list:
    return [
        {
            "symbol": "AAPL",
            "close": 150.0,
            "volume": 100_000,
            "change_percent": 0.5,
        },
        {
            "symbol": "NVDA",
            "close": 900.0,
            "volume": 2_000_000,
            "change_percent": 3.0,
        },
        {
            "symbol": "MSFT",
            "close": 400.0,
            "volume": 50_000,
            "change_percent": 0.2,
        },
    ]


def test_run_user_check_fires_price_and_screening_together(db_users) -> None:
    """Price-symbol quote fetch must not shrink screening off the snapshot."""
    user_a, user_b = db_users
    save_user_alerts_config(user_a, _mixed_config("aapl-a", "volume-a"))
    save_user_alerts_config(user_b, _mixed_config("aapl-b", "volume-b"))

    assert get_watch(user_a, "aapl-a")["alert"]["condition"]["type"] == "price_threshold"
    assert get_watch(user_a, "volume-a")["alert"]["condition"]["type"] == "screening_match"
    assert list_enabled_symbols() == ["AAPL"]

    with patch(
        "src.alerts.market_snapshot.load_market_snapshot",
        return_value=("2026-06-09", {"AAPL": 150.0}, _mixed_snapshot_stocks()),
    ) as load_snapshot:
        with patch("src.alerts.alert_engine.LogNotifier.send", return_value=True) as send:
            with patch("src.alerts.alert_worker.run_db_worker_cycle") as mock_cycle:
                result = alert_worker.run_user_check(user_a)

    assert result["triggered"] == 2
    assert result["last_data_date"] == "2026-06-09"
    assert result["message"] is None
    events_by_id = {event["alert_id"]: event for event in result["events"]}
    assert events_by_id["aapl-a"]["condition_type"] == "price_threshold"
    assert events_by_id["aapl-a"]["symbols"] == ["AAPL"]
    assert events_by_id["volume-a"]["condition_type"] == "screening_match"
    assert events_by_id["volume-a"]["symbols"] == ["NVDA"]
    assert send.call_count == 2
    mock_cycle.assert_not_called()
    load_snapshot.assert_called_once_with(["AAPL"], fetch_missing_quotes=True)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT user_id, alert_id FROM alert_trigger_state ORDER BY alert_id"
        ).fetchall()
    assert [(row["user_id"], row["alert_id"]) for row in rows] == [
        (user_a, "aapl-a"),
        (user_a, "volume-a"),
    ]


def test_mixed_tenant_orchestrator_enqueues_only_price_symbol(db_users) -> None:
    """Enabled screening rows persist but must not enter the symbol job queue."""
    user_a, _user_b = db_users
    save_user_alerts_config(user_a, _mixed_config())

    assert get_watch(user_a, "volume-spike") is not None
    assert list_enabled_symbols() == ["AAPL"]

    with patch(
        "src.alerts.alert_orchestrator.load_market_snapshot",
        return_value=("2026-06-09", {"AAPL": 150.0}, _mixed_snapshot_stocks()),
    ) as mock_snapshot:
        tick = run_orchestrator_tick()

    mock_snapshot.assert_called_once_with(["AAPL"], fetch_missing_quotes=True)
    assert tick["enqueued"] == 1
    assert tick["last_data_date"] == "2026-06-09"
    assert tick["message"] is None
    assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 1

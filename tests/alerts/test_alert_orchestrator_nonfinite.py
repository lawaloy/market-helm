"""Orchestrator must not enqueue Inf/NaN prices as evaluate_symbol jobs."""

from unittest.mock import patch

import pytest

from src.alerts.alert_orchestrator import run_orchestrator_tick
from src.storage.alert_jobs import JOB_EVALUATE_SYMBOL, pending_job_count
from src.storage.alert_watches import sync_watches_from_config
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "orch-nf.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("orch-nf@example.com", "password123")["id"]


def _watch(alert_id, symbol):
    return {
        "id": alert_id,
        "enabled": True,
        "condition": {
            "type": "price_threshold",
            "symbol": symbol,
            "operator": "less_than",
            "value": 999,
        },
    }


@pytest.mark.parametrize("bad_price", [float("nan"), float("inf"), float("-inf"), "not-a-price"])
@patch("src.alerts.alert_orchestrator.load_market_snapshot")
def test_skips_nonfinite_or_invalid_prices(mock_snapshot, db_user, bad_price):
    sync_watches_from_config(
        db_user,
        {
            "defaults": {},
            "alerts": [_watch("aapl", "AAPL"), _watch("msft", "MSFT")],
        },
    )
    mock_snapshot.return_value = (
        "2026-06-09",
        {"AAPL": bad_price, "MSFT": 420.0},
        [],
    )

    result = run_orchestrator_tick()

    assert result["enqueued"] == 1
    assert result["message"] is None
    assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 1


@patch("src.alerts.alert_orchestrator.load_market_snapshot")
def test_all_nonfinite_prices_message(mock_snapshot, db_user):
    sync_watches_from_config(
        db_user,
        {
            "defaults": {},
            "alerts": [_watch("aapl", "AAPL")],
        },
    )
    mock_snapshot.return_value = ("2026-06-09", {"AAPL": float("nan")}, [])

    result = run_orchestrator_tick()

    assert result["enqueued"] == 0
    assert result["message"] == "No priced symbols for enabled watches."
    assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 0

"""Tests for alert orchestrator."""

from unittest.mock import patch

import pytest

from src.alerts.alert_orchestrator import run_orchestrator_tick
from src.storage.alert_jobs import JOB_EVALUATE_SYMBOL, pending_job_count
from src.storage.alert_watches import sync_watches_from_config
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "orch.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    user = create_user("orch@example.com", "password123")
    return user["id"]


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


class TestAlertOrchestrator:
    def test_no_watches_message(self, db_user):
        result = run_orchestrator_tick()
        assert result["enqueued"] == 0
        assert "No enabled watches" in (result["message"] or "")

    @patch("src.alerts.alert_orchestrator.load_market_snapshot")
    def test_enqueues_symbol_jobs(self, mock_snapshot, db_user):
        sync_watches_from_config(
            db_user,
            {
                "defaults": {},
                "alerts": [_watch("a1", "AAPL")],
            },
        )
        mock_snapshot.return_value = ("2026-06-09", {"AAPL": 180.0}, [])

        result = run_orchestrator_tick()
        assert result["enqueued"] == 1
        assert result["last_data_date"] == "2026-06-09"
        assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 1

    @patch("src.alerts.alert_orchestrator.load_market_snapshot")
    def test_no_market_data_message(self, mock_snapshot, db_user):
        sync_watches_from_config(
            db_user,
            {
                "defaults": {},
                "alerts": [_watch("a1", "AAPL")],
            },
        )
        mock_snapshot.return_value = ("2026-06-09", {}, [])

        result = run_orchestrator_tick()

        assert result["enqueued"] == 0
        assert result["last_data_date"] == "2026-06-09"
        assert result["message"] == "No market data available."
        assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 0
        mock_snapshot.assert_called_once_with(["AAPL"], fetch_missing_quotes=True)

    @patch("src.alerts.alert_orchestrator.load_market_snapshot")
    def test_skips_watched_symbols_without_prices(self, mock_snapshot, db_user):
        sync_watches_from_config(
            db_user,
            {
                "defaults": {},
                "alerts": [_watch("aapl", "AAPL"), _watch("msft", "MSFT")],
            },
        )
        mock_snapshot.return_value = ("2026-06-09", {"AAPL": 180.0}, [])

        result = run_orchestrator_tick()

        assert result["enqueued"] == 1
        assert result["message"] is None
        assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 1
        mock_snapshot.assert_called_once_with(["AAPL", "MSFT"], fetch_missing_quotes=True)

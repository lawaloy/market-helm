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
                "alerts": [
                    {
                        "id": "a1",
                        "enabled": True,
                        "condition": {
                            "type": "price_threshold",
                            "symbol": "AAPL",
                            "operator": "less_than",
                            "value": 999,
                        },
                    }
                ],
            },
        )
        mock_snapshot.return_value = ("2026-06-09", {"AAPL": 180.0}, [])

        result = run_orchestrator_tick()
        assert result["enqueued"] == 1
        assert result["last_data_date"] == "2026-06-09"
        assert pending_job_count([JOB_EVALUATE_SYMBOL]) == 1

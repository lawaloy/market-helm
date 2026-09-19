"""Hosted watch indexing and job evaluation for RSI / compound rules."""

from unittest.mock import patch

import pytest

from src.alerts.job_processor import process_job_queue
from src.storage.alert_jobs import JOB_DELIVER, JOB_EVALUATE_SYMBOL, enqueue_job, pending_job_count
from src.storage.alert_watches import list_watches_for_symbol, sync_watches_from_config
from src.storage.database import init_database
from src.storage.users import create_user


@pytest.fixture
def db_user(tmp_path, monkeypatch):
    db_path = tmp_path / "rsi-compound.db"
    monkeypatch.setenv("MARKET_HELM_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    init_database()
    return create_user("rsi@example.com", "password123")["id"]


def _falling_closes(n: int = 20, start: float = 100.0) -> list[float]:
    return [start - i for i in range(n)]


def test_rsi_watch_is_indexed_and_evaluated(db_user):
    sync_watches_from_config(
        db_user,
        {
            "defaults": {},
            "alerts": [
                {
                    "id": "aapl-rsi",
                    "name": "AAPL RSI",
                    "enabled": True,
                    "cooldown_minutes": 0,
                    "condition": {
                        "type": "rsi_threshold",
                        "symbol": "AAPL",
                        "period": 14,
                        "operator": "less_than",
                        "value": 30,
                    },
                    "notifications": ["log"],
                }
            ],
        },
    )
    watches = list_watches_for_symbol("AAPL")
    assert len(watches) == 1
    assert watches[0]["condition_type"] == "rsi_threshold"

    enqueue_job(JOB_EVALUATE_SYMBOL, {"symbol": "AAPL", "price": 80.0})
    with patch(
        "src.alerts.job_processor.closes_by_symbol",
        return_value={"AAPL": _falling_closes()},
    ), patch("src.alerts.alert_engine.LogNotifier.send", return_value=True):
        stats = process_job_queue("test-worker")

    assert stats["evaluated"] == 1
    assert stats["delivered"] == 1
    assert pending_job_count([JOB_DELIVER]) == 0


def test_single_symbol_compound_is_indexed(db_user):
    sync_watches_from_config(
        db_user,
        {
            "defaults": {},
            "alerts": [
                {
                    "id": "aapl-combo",
                    "name": "AAPL Combo",
                    "enabled": True,
                    "cooldown_minutes": 0,
                    "condition": {
                        "type": "compound",
                        "op": "and",
                        "conditions": [
                            {
                                "type": "price_threshold",
                                "symbol": "AAPL",
                                "operator": "less_than",
                                "value": 150,
                            },
                            {
                                "type": "rsi_threshold",
                                "symbol": "AAPL",
                                "period": 14,
                                "operator": "less_than",
                                "value": 30,
                            },
                        ],
                    },
                    "notifications": ["log"],
                }
            ],
        },
    )
    watches = list_watches_for_symbol("AAPL")
    assert len(watches) == 1
    assert watches[0]["condition_type"] == "compound"

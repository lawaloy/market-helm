"""History summary day averages must ignore Inf/NaN cells (match projector)."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import dashboard.backend.api.history
from dashboard.backend.main import app


@pytest.fixture
def client():
    yield TestClient(app)


def test_history_summary_ignores_inf_when_averaging_confidence_and_expected(client):
    """A single Inf must not zero-out finite peers via mean→_safe_float."""
    loader = MagicMock()
    loader.get_available_dates.return_value = ["2026-01-15"]
    loader.load_projections.return_value = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "GOOG"],
            "name": ["Apple", "Microsoft", "Alphabet"],
            "confidence": [80.0, float("inf"), 60.0],
            "expected_change_percent": [2.0, float("-inf"), 1.0],
            "recommendation": ["BUY", "HOLD", "BUY"],
        }
    )

    with patch.object(
        dashboard.backend.api.history, "get_data_loader", return_value=loader
    ), patch.object(
        dashboard.backend.api.history,
        "load_index_symbol_names",
        return_value={},
    ):
        r = client.get("/api/history/summary", params={"days": 7})

    assert r.status_code == 200
    point = r.json()["data"][0]
    assert point["averageConfidence"] == 70.0
    assert point["expectedMarketMove"] == 1.5
    assert point["sentiment"] == "Bullish"


def test_history_summary_all_inf_means_are_finite_neutral(client):
    loader = MagicMock()
    loader.get_available_dates.return_value = ["2026-01-15"]
    loader.load_projections.return_value = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT"],
            "name": ["Apple", "Microsoft"],
            "confidence": [float("inf"), float("-inf")],
            "expected_change_percent": [float("inf"), float("nan")],
            "recommendation": ["HOLD", "HOLD"],
        }
    )

    with patch.object(
        dashboard.backend.api.history, "get_data_loader", return_value=loader
    ), patch.object(
        dashboard.backend.api.history,
        "load_index_symbol_names",
        return_value={},
    ):
        r = client.get("/api/history/summary", params={"days": 7})

    assert r.status_code == 200
    point = r.json()["data"][0]
    assert point["averageConfidence"] == 0.0
    assert point["expectedMarketMove"] == 0.0
    assert point["sentiment"] == "Neutral"

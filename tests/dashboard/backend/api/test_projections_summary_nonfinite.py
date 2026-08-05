"""Projections summary averages must ignore Inf/NaN cells (match projector/history)."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import dashboard.backend.api.projections
from dashboard.backend.main import app


@pytest.fixture
def client():
    yield TestClient(app)


def test_projections_summary_ignores_inf_when_averaging_confidence_and_expected(client):
    """A single Inf must not zero-out finite peers via mean→_finite_float."""
    loader = MagicMock()
    loader.get_latest_date.return_value = "2026-01-15"
    loader.load_projections.return_value = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "GOOG"],
            "confidence": [80.0, float("inf"), 60.0],
            "expected_change_percent": [2.0, float("-inf"), 1.0],
            "recommendation": ["BUY", "HOLD", "BUY"],
            "trend": ["Bullish", "Neutral", "Bullish"],
            "risk_level": ["Low", "Medium", "Low"],
        }
    )

    with patch.object(
        dashboard.backend.api.projections, "get_data_loader", return_value=loader
    ):
        r = client.get("/api/projections/summary")

    assert r.status_code == 200
    data = r.json()
    assert data["averageConfidence"] == 70.0
    assert data["expectedMarketMove"] == 1.5
    assert data["sentiment"] == "Bullish"
    assert data["totalProjections"] == 3


def test_projections_summary_all_inf_means_are_finite_neutral(client):
    loader = MagicMock()
    loader.get_latest_date.return_value = "2026-01-15"
    loader.load_projections.return_value = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT"],
            "confidence": [float("inf"), float("-inf")],
            "expected_change_percent": [float("inf"), float("nan")],
            "recommendation": ["HOLD", "HOLD"],
            "trend": ["Neutral", "Neutral"],
            "risk_level": ["Medium", "Medium"],
        }
    )

    with patch.object(
        dashboard.backend.api.projections, "get_data_loader", return_value=loader
    ):
        r = client.get("/api/projections/summary")

    assert r.status_code == 200
    data = r.json()
    assert data["averageConfidence"] == 0.0
    assert data["expectedMarketMove"] == 0.0
    assert data["sentiment"] == "Neutral"
    assert data["totalProjections"] == 2

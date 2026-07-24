"""History summary must drop blank/sentinel symbols from list + name map."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import dashboard.backend.api.history
from dashboard.backend.main import app


@pytest.fixture
def client():
    yield TestClient(app)


def test_history_summary_skips_none_nan_blank_and_sentinel_symbols(client):
    """None/NaN/blank/NONE/NAN must never appear in symbols or names."""
    loader = MagicMock()
    loader.get_available_dates.return_value = ["2026-01-15"]
    loader.load_projections.return_value = pd.DataFrame(
        {
            "symbol": ["AAPL", None, float("nan"), "", "  ", "NONE", "NAN", " msft "],
            "name": [
                "Apple Inc.",
                "Nope",
                "Nope",
                "Nope",
                "Nope",
                "Nope",
                "Nope",
                "Microsoft",
            ],
            "confidence": [80.0] * 8,
            "expected_change_percent": [1.5] * 8,
            "recommendation": ["BUY"] * 8,
        }
    )

    with patch.object(
        dashboard.backend.api.history, "get_data_loader", return_value=loader
    ), patch.object(
        dashboard.backend.api.history,
        "load_index_symbol_names",
        return_value={"AAPL": "Apple Inc.", "MSFT": "Microsoft"},
    ):
        r = client.get("/api/history/summary", params={"days": 7})

    assert r.status_code == 200
    data = r.json()
    assert data["symbols"] == ["AAPL", "MSFT"]
    assert "NONE" not in data["symbols"]
    assert "NAN" not in data["symbols"]
    assert "" not in data["symbols"]
    assert data["names"]["AAPL"] == "Apple Inc."
    assert data["names"]["MSFT"] == "Microsoft"
    assert "NONE" not in data["names"]
    assert "NAN" not in data["names"]

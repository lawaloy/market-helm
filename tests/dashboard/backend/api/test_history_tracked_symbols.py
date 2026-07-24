"""Tracked symbols empty-catalog fallback must normalize dirty projection symbols."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import dashboard.backend.api.history
from dashboard.backend.main import app


@pytest.fixture
def client():
    yield TestClient(app)


def test_tracked_symbols_empty_catalog_fallback_skips_sentinels(client):
    """When index+projection catalog is empty, fallback still drops None/NaN/NONE."""
    loader = MagicMock()
    loader.get_latest_date.return_value = "2026-01-15"
    loader.load_projections.return_value = pd.DataFrame(
        {
            "symbol": [None, float("nan"), "", "NONE", "NAN", " goog ", "aapl"],
            "name": ["Nope"] * 5 + ["Alphabet", "Apple"],
        }
    )

    with patch.object(
        dashboard.backend.api.history, "get_data_loader", return_value=loader
    ), patch.object(
        dashboard.backend.api.history, "build_symbol_catalog", return_value=([], {})
    ), patch.object(
        dashboard.backend.api.history,
        "load_index_symbol_names",
        return_value={},
    ):
        r = client.get("/api/history/symbols")

    assert r.status_code == 200
    data = r.json()
    assert data["date"] == "2026-01-15"
    assert data["symbols"] == ["AAPL", "GOOG"]
    assert "NONE" not in data["symbols"]
    assert "NAN" not in data["symbols"]
    assert "" not in data["symbols"]
    assert set(data["names"]) == {"AAPL", "GOOG"}
    assert "NONE" not in data["names"]
    assert "NAN" not in data["names"]

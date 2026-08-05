"""Opportunities must soft-fail dirty name/reason cells (NaN → Pydantic 500)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest


@pytest.fixture
def temp_data_dir():
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def client(temp_data_dir):
    from dashboard.backend.services.data_loader import DataLoader
    import dashboard.backend.api.projections

    loader = DataLoader(data_dir=temp_data_dir)
    with patch.object(
        dashboard.backend.api.projections, "get_data_loader", return_value=loader
    ):
        from fastapi.testclient import TestClient
        from dashboard.backend.main import app

        yield TestClient(app)


def test_opportunities_falls_back_when_name_and_reason_are_nan(
    client, temp_data_dir
) -> None:
    """NaN name/reason previously failed Opportunity str validation → 500."""
    pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "close": [150.0],
            "volume": [1_000],
        }
    ).to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)
    pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "name": [float("nan")],
            "target_mid": [160.0],
            "expected_change_percent": [5.0],
            "confidence": [90],
            "recommendation": ["STRONG BUY"],
            "risk_level": ["Low"],
            "trend": ["Bullish"],
            "momentum_score": [1.2],
            "volatility_score": [0.3],
            "reason": [float("nan")],
        }
    ).to_csv(temp_data_dir / "projections_2026-01-15.csv", index=False)

    r = client.get(
        "/api/projections/opportunities",
        params={"type": "STRONG_BUY", "limit": 10},
    )
    assert r.status_code == 200
    row = r.json()["opportunities"][0]
    assert row["symbol"] == "AAPL"
    assert row["name"] == "AAPL"
    assert row["reason"] == ""
    assert row["risk"] == "Low"
    assert row["trend"] == "Bullish"

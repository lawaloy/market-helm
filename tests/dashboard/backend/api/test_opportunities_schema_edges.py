"""Opportunities must soft-fail missing daily symbol / risk / trend columns."""

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


def _write_projection(temp_data_dir: Path, **overrides) -> None:
    row = {
        "symbol": ["AAPL"],
        "name": ["Apple"],
        "target_mid": [160.0],
        "expected_change_percent": [5.0],
        "confidence": [90],
        "recommendation": ["STRONG BUY"],
        "risk_level": ["Low"],
        "trend": ["Bullish"],
        "momentum_score": [1.2],
        "volatility_score": [0.3],
        "reason": ["momentum"],
    }
    row.update(overrides)
    pd.DataFrame(row).to_csv(
        temp_data_dir / "projections_2026-01-15.csv", index=False
    )


def test_opportunities_defaults_when_daily_symbol_column_missing(
    client, temp_data_dir
) -> None:
    """Daily CSV without symbol previously KeyError'd opportunities → 500."""
    pd.DataFrame(
        {
            "close": [151.25],
            "volume": [42_000],
        }
    ).to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)
    _write_projection(temp_data_dir)

    r = client.get(
        "/api/projections/opportunities",
        params={"type": "STRONG_BUY", "limit": 10},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    row = data["opportunities"][0]
    assert row["symbol"] == "AAPL"
    assert row["currentPrice"] == 0.0
    assert row["volume"] == 0


def test_opportunities_defaults_missing_risk_and_trend(client, temp_data_dir) -> None:
    """Legacy projection CSVs without risk_level/trend must still list cards."""
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
            "name": ["Apple"],
            "target_mid": [160.0],
            "expected_change_percent": [5.0],
            "confidence": [90],
            "recommendation": ["STRONG BUY"],
            "momentum_score": [1.2],
            "volatility_score": [0.3],
            "reason": ["momentum"],
        }
    ).to_csv(temp_data_dir / "projections_2026-01-15.csv", index=False)

    r = client.get(
        "/api/projections/opportunities",
        params={"type": "STRONG_BUY", "limit": 10},
    )
    assert r.status_code == 200
    row = r.json()["opportunities"][0]
    assert row["risk"] == "Unknown"
    assert row["trend"] == "Neutral"
    assert row["currentPrice"] == 150.0

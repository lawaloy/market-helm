"""Opportunities must expose recommendation separately from trend."""

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


def _write_fixtures(temp_data_dir: Path) -> None:
    pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT"],
            "name": ["Apple", "Microsoft"],
            "close": [150.0, 400.0],
            "change": [1.0, -1.0],
            "change_percent": [0.7, -0.2],
            "volume": [1_000, 2_000],
        }
    ).to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)
    pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT"],
            "name": ["Apple", "Microsoft"],
            "target_mid": [160.0, 390.0],
            "expected_change_percent": [5.0, -2.5],
            "confidence": [90, 70],
            "recommendation": ["STRONG BUY", "SELL"],
            "risk_level": ["Low", "High"],
            "trend": ["Bullish", "Bearish"],
            "momentum_score": [1.2, -0.4],
            "volatility_score": [0.3, 0.8],
            "reason": ["momentum", "weakness"],
        }
    ).to_csv(temp_data_dir / "projections_2026-01-15.csv", index=False)


def test_opportunities_include_recommendation_matching_filter_type(
    client, temp_data_dir
) -> None:
    """Table filters need recommendation; trend alone is Bullish/Bearish."""
    _write_fixtures(temp_data_dir)

    r = client.get(
        "/api/projections/opportunities",
        params={"type": "STRONG_BUY", "limit": 10},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    row = data["opportunities"][0]
    assert row["symbol"] == "AAPL"
    assert row["recommendation"] == "STRONG BUY"
    assert row["trend"] == "Bullish"


def test_opportunities_sell_bucket_keeps_trend_independent(
    client, temp_data_dir
) -> None:
    _write_fixtures(temp_data_dir)

    r = client.get(
        "/api/projections/opportunities",
        params={"type": "SELL", "limit": 10},
    )
    assert r.status_code == 200
    row = r.json()["opportunities"][0]
    assert row["symbol"] == "MSFT"
    assert row["recommendation"] == "SELL"
    assert row["trend"] == "Bearish"

"""Opportunities must coerce blank/NaN label sentinels instead of leaking them."""

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


def _write_daily(temp_data_dir: Path) -> None:
    pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "close": [150.0],
            "volume": [1_000],
        }
    ).to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)


def _write_projection(temp_data_dir: Path, risk_level, trend) -> None:
    pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "name": ["Apple"],
            "target_mid": [160.0],
            "expected_change_percent": [5.0],
            "confidence": [90],
            "recommendation": ["STRONG BUY"],
            "risk_level": [risk_level],
            "trend": [trend],
            "momentum_score": [1.2],
            "volatility_score": [0.3],
            "reason": ["momentum"],
        }
    ).to_csv(temp_data_dir / "projections_2026-01-15.csv", index=False)


@pytest.mark.parametrize(
    "risk_level,trend",
    [
        ("nan", "NaN"),
        ("none", "<NA>"),
        ("  ", "None"),
        (float("nan"), float("nan")),
    ],
)
def test_opportunities_coerces_label_sentinels(
    client, temp_data_dir, risk_level, trend
) -> None:
    _write_daily(temp_data_dir)
    _write_projection(temp_data_dir, risk_level=risk_level, trend=trend)

    r = client.get(
        "/api/projections/opportunities",
        params={"type": "STRONG_BUY", "limit": 10},
    )
    assert r.status_code == 200
    row = r.json()["opportunities"][0]
    assert row["risk"] == "Unknown"
    assert row["trend"] == "Neutral"


def test_opportunities_keeps_real_labels(client, temp_data_dir) -> None:
    _write_daily(temp_data_dir)
    _write_projection(temp_data_dir, risk_level="Low", trend="Bullish")

    r = client.get(
        "/api/projections/opportunities",
        params={"type": "STRONG_BUY", "limit": 10},
    )
    assert r.status_code == 200
    row = r.json()["opportunities"][0]
    assert row["risk"] == "Low"
    assert row["trend"] == "Bullish"

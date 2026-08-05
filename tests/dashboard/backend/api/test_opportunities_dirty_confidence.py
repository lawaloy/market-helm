"""Opportunities must soft-fail dirty confidence cells before nlargest ranking."""

from __future__ import annotations

import math
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


def _write_csvs(temp_data_dir: Path, confidence_values) -> None:
    n = len(confidence_values)
    symbols = [f"T{i}" for i in range(n)]
    pd.DataFrame(
        {
            "symbol": symbols,
            "name": [f"Ticker {i}" for i in range(n)],
            "target_mid": [160.0] * n,
            "expected_change_percent": [5.0] * n,
            "confidence": list(confidence_values),
            "recommendation": ["BUY"] * n,
            "risk_level": ["Low"] * n,
            "trend": ["Bullish"] * n,
            "momentum_score": [1.2] * n,
            "volatility_score": [0.3] * n,
            "reason": ["momentum"] * n,
        }
    ).to_csv(temp_data_dir / "projections_2026-01-15.csv", index=False)
    pd.DataFrame(
        {
            "symbol": symbols,
            "close": [150.0] * n,
            "volume": [10_000] * n,
        }
    ).to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)


def test_opportunities_soft_fails_string_confidence_column(client, temp_data_dir) -> None:
    """Object/str confidence previously TypeError'd nlargest → 500 the bucket."""
    _write_csvs(temp_data_dir, ["high", "90", "bad", "40"])

    r = client.get(
        "/api/projections/opportunities",
        params={"type": "BUY", "limit": 10},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 2
    symbols = [row["symbol"] for row in data["opportunities"]]
    assert symbols == ["T1", "T3"]
    assert data["opportunities"][0]["confidence"] == 90
    assert data["opportunities"][1]["confidence"] == 40


def test_opportunities_skips_nonfinite_confidence_before_ranking(
    client, temp_data_dir
) -> None:
    """Inf/NaN confidence must not win nlargest slots or abort the endpoint."""
    _write_csvs(temp_data_dir, [math.inf, float("nan"), 70.0, -math.inf])

    r = client.get(
        "/api/projections/opportunities",
        params={"type": "BUY", "limit": 10},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    assert data["opportunities"][0]["symbol"] == "T2"
    assert data["opportunities"][0]["confidence"] == 70

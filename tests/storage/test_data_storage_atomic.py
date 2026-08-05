"""DataStorage saves must not truncate existing files when a write fails mid-way."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.storage.data_storage import DataStorage


@pytest.fixture
def storage(tmp_path):
    return DataStorage(data_dir=str(tmp_path))


def test_save_daily_data_preserves_prior_file_when_replace_fails(storage, tmp_path):
    target = date(2026, 6, 9)
    first = storage.save_daily_data(
        [{"symbol": "AAPL", "name": "Apple", "close": 150.0}],
        date=target,
    )
    assert first is not None
    prior = Path(first).read_text(encoding="utf-8")

    real_replace = Path.replace

    def boom(self, target_path):
        if self.name.endswith(".csv.tmp"):
            raise OSError("simulated crash before replace")
        return real_replace(self, target_path)

    with patch.object(Path, "replace", boom):
        with pytest.raises(OSError, match="simulated crash"):
            storage.save_daily_data(
                [{"symbol": "MSFT", "name": "Microsoft", "close": 400.0}],
                date=target,
            )

    assert Path(first).read_text(encoding="utf-8") == prior
    assert list(tmp_path.glob("daily_data_*.csv.tmp")) == []


def test_save_summary_preserves_prior_file_when_replace_fails(storage, tmp_path):
    target = date(2026, 6, 9)
    path = Path(storage.save_summary({"total_stocks": 2}, date=target))
    prior = path.read_text(encoding="utf-8")
    assert json.loads(prior)["total_stocks"] == 2

    real_replace = Path.replace

    def boom(self, target_path):
        if self.name.endswith(".json.tmp"):
            raise OSError("simulated crash before replace")
        return real_replace(self, target_path)

    with patch.object(Path, "replace", boom):
        with pytest.raises(OSError, match="simulated crash"):
            storage.save_summary({"total_stocks": 99}, date=target)

    assert path.read_text(encoding="utf-8") == prior
    assert json.loads(path.read_text(encoding="utf-8"))["total_stocks"] == 2
    assert list(tmp_path.glob("summary_*.json.tmp")) == []


def test_save_projections_preserves_prior_csv_when_replace_fails(storage, tmp_path):
    target = date(2026, 6, 9)
    path = Path(
        storage.save_projections(
            {
                "AAPL": {
                    "symbol": "AAPL",
                    "name": "Apple",
                    "current_price": 150.0,
                    "target_low": 140.0,
                    "target_mid": 155.0,
                    "target_high": 170.0,
                    "expected_change_percent": 3.0,
                    "recommendation": "BUY",
                    "confidence": 80,
                    "trend": "up",
                    "momentum_score": 1.0,
                    "volatility_score": 0.2,
                    "risk_level": "LOW",
                    "reason": "steady",
                    "projection_date": "2026-06-14",
                    "generated_at": "2026-06-09T12:00:00",
                }
            },
            date=target,
        )
    )
    prior = path.read_text(encoding="utf-8")
    assert "AAPL" in prior

    real_replace = Path.replace

    def boom(self, target_path):
        if self.name.endswith(".csv.tmp"):
            raise OSError("simulated crash before replace")
        return real_replace(self, target_path)

    with patch.object(Path, "replace", boom):
        with pytest.raises(OSError, match="simulated crash"):
            storage.save_projections(
                {
                    "MSFT": {
                        "symbol": "MSFT",
                        "name": "Microsoft",
                        "current_price": 400.0,
                        "target_low": 390.0,
                        "target_mid": 410.0,
                        "target_high": 430.0,
                        "expected_change_percent": 2.0,
                        "recommendation": "HOLD",
                        "confidence": 70,
                        "trend": "flat",
                        "momentum_score": 0.5,
                        "volatility_score": 0.3,
                        "risk_level": "MED",
                        "reason": "mixed",
                        "projection_date": "2026-06-14",
                        "generated_at": "2026-06-09T12:00:00",
                    }
                },
                date=target,
            )

    assert path.read_text(encoding="utf-8") == prior
    assert "AAPL" in path.read_text(encoding="utf-8")
    df = pd.read_csv(path)
    assert list(df["symbol"]) == ["AAPL"]

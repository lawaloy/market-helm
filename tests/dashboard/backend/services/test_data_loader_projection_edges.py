"""Projection date coercion and corrupt-projection soft-fails for DataLoader."""

from datetime import date, timedelta
from pathlib import Path
import shutil
import tempfile

import pandas as pd
import pytest


@pytest.fixture
def temp_data_dir():
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def loader(temp_data_dir):
    from dashboard.backend.services.data_loader import DataLoader

    return DataLoader(data_dir=temp_data_dir)


class TestProjectionAccuracyInvalidDates:
    def test_compute_projection_accuracy_ignores_legacy_bad_projection_date(
        self, loader, temp_data_dir
    ):
        """The shared evaluator derives the exact session instead of trusting a dirty field."""
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "close": [100.0],
                "change_percent": [0.0],
            }
        ).to_csv(temp_data_dir / "daily_data_2026-01-05.csv", index=False)
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "close": [110.0],
                "change_percent": [1.0],
            }
        ).to_csv(temp_data_dir / "daily_data_2026-01-12.csv", index=False)
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "target_mid": [100.0],
                "recommendation": ["HOLD"],
                "projection_date": ["not-a-date"],
            }
        ).to_csv(temp_data_dir / "projections_2026-01-05.csv", index=False)

        out = loader.compute_projection_accuracy(days=90)

        assert out["summary"]["sampleCount"] == 1
        sample = out["samples"][0]
        assert sample["targetDate"] == "2026-01-12"
        assert sample["actualDate"] == "2026-01-12"
        assert sample["absErrorPct"] == 9.091


class TestProjectionAccuracyRecommendationSentinels:
    def test_nan_recommendation_becomes_unknown(self, loader, temp_data_dir):
        """NaN recommendation cells must not create a \"nan\" accuracy bucket."""
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "close": [100.0],
                "change_percent": [0.0],
            }
        ).to_csv(temp_data_dir / "daily_data_2026-01-05.csv", index=False)
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "close": [110.0],
                "change_percent": [1.0],
            }
        ).to_csv(temp_data_dir / "daily_data_2026-01-12.csv", index=False)
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "target_mid": [100.0],
                "recommendation": [float("nan")],
                "projection_date": ["2026-01-12"],
            }
        ).to_csv(temp_data_dir / "projections_2026-01-05.csv", index=False)

        out = loader.compute_projection_accuracy(days=90)

        assert out["summary"]["sampleCount"] == 1
        assert out["samples"][0]["recommendation"] == "UNKNOWN"
        assert "nan" not in {k.lower() for k in out["summary"]["byRecommendation"]}
        assert "UNKNOWN" in out["summary"]["byRecommendation"]
        assert out["summary"]["byRecommendation"]["UNKNOWN"]["count"] == 1


class TestHistoricalCorruptProjections:
    def test_load_historical_data_keeps_daily_when_projections_unreadable(
        self, loader, temp_data_dir
    ):
        """A corrupt projections CSV must not hide valid daily history for the symbol."""
        recent = (date.today() - timedelta(days=1)).isoformat()
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "close": [155.0],
                "change_percent": [0.5],
                "volume": [1_000],
            }
        ).to_csv(temp_data_dir / f"daily_data_{recent}.csv", index=False)
        (temp_data_dir / f"projections_{recent}.csv").write_text(
            'col1,col2\n1,"unclosed',
            encoding="utf-8",
        )

        rows = loader.load_historical_data("AAPL", days=7)

        assert len(rows) == 1
        assert rows[0]["date"] == recent
        assert rows[0]["close"] == 155.0
        assert "projection" not in rows[0]

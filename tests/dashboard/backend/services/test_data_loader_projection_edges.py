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


class TestProjectionTargetDateEdges:
    @pytest.mark.parametrize(
        "raw",
        [
            "not-a-date",
            "01/15/2026",
            "2026-13-40",
            "",
            "   ",
            float("nan"),
        ],
    )
    def test_invalid_projection_date_falls_back_to_run_plus_five(self, loader, raw):
        """Dirty CSV projection_date cells must not crash; use run date + 5 days."""
        assert loader._projection_target_date(
            {"projection_date": raw}, "2026-01-01"
        ) == "2026-01-06"

    def test_datetime_prefix_is_accepted(self, loader):
        """ISO datetime strings keep the YYYY-MM-DD prefix."""
        assert (
            loader._projection_target_date(
                {"projection_date": "2026-02-01T15:30:00"}, "2026-01-01"
            )
            == "2026-02-01"
        )


class TestProjectionAccuracyInvalidDates:
    def test_compute_projection_accuracy_falls_back_on_bad_projection_date(
        self, loader, temp_data_dir
    ):
        """Invalid projection_date scores against run_date + 5 when that close exists."""
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "close": [100.0],
                "change_percent": [0.0],
            }
        ).to_csv(temp_data_dir / "daily_data_2026-01-01.csv", index=False)
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "close": [110.0],
                "change_percent": [1.0],
            }
        ).to_csv(temp_data_dir / "daily_data_2026-01-06.csv", index=False)
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "target_mid": [100.0],
                "recommendation": ["HOLD"],
                "projection_date": ["not-a-date"],
            }
        ).to_csv(temp_data_dir / "projections_2026-01-01.csv", index=False)

        out = loader.compute_projection_accuracy(days=90)

        assert out["summary"]["sampleCount"] == 1
        sample = out["samples"][0]
        assert sample["targetDate"] == "2026-01-06"
        assert sample["actualDate"] == "2026-01-06"
        assert sample["absErrorPct"] == 10.0


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

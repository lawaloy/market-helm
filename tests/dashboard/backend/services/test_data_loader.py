"""Tests for dashboard data loader service."""

import os
import tempfile
import shutil
import json
import time
import pandas as pd
from pathlib import Path

import pytest


@pytest.fixture
def temp_data_dir():
    """Create temp data directory."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def loader(temp_data_dir):
    """Create DataLoader with temp directory."""
    from dashboard.backend.services.data_loader import DataLoader
    return DataLoader(data_dir=temp_data_dir)


class TestDataLoader:
    """Test DataLoader class."""

    def test_raises_for_missing_data_dir(self):
        """DataLoader raises when data directory does not exist."""
        from dashboard.backend.services.data_loader import DataLoader

        with pytest.raises(ValueError, match="Data directory not found"):
            DataLoader(data_dir=Path("/nonexistent/path"))

    def test_get_latest_date_returns_none_when_empty(self, loader):
        """get_latest_date returns None when no daily data files."""
        assert loader.get_latest_date() is None

    def test_load_daily_data_raises_when_no_files(self, loader):
        """load_daily_data raises when no files exist."""
        with pytest.raises(ValueError, match="No daily data files found"):
            loader.load_daily_data()

    def test_load_summary_raises_when_no_files(self, loader):
        """load_summary raises when no summary files exist."""
        with pytest.raises(ValueError, match="No summary files found"):
            loader.load_summary()

    def test_load_daily_data_returns_dataframe(self, loader, temp_data_dir):
        """load_daily_data returns correct DataFrame."""
        df = pd.DataFrame({
            "symbol": ["AAPL", "GOOGL"],
            "close": [150.0, 2800.0],
            "change_percent": [1.0, -0.5],
        })
        df.to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)

        result = loader.load_daily_data()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "symbol" in result.columns

    def test_load_summary_returns_dict(self, loader, temp_data_dir):
        """load_summary returns correct dict."""
        summary = {"date": "2026-01-15", "analysis": {}}
        with open(temp_data_dir / "summary_2026-01-15.json", "w") as f:
            json.dump(summary, f)

        result = loader.load_summary()
        assert isinstance(result, dict)
        assert result["date"] == "2026-01-15"

    def test_load_summary_raises_value_error_on_corrupt_json(self, loader, temp_data_dir):
        """Corrupt summary JSON raises ValueError so APIs can map to 404."""
        (temp_data_dir / "summary_2026-01-15.json").write_text(
            "{not-json", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="Summary file unreadable"):
            loader.load_summary()

    def test_load_daily_data_raises_value_error_on_corrupt_csv(self, loader, temp_data_dir):
        """Unreadable daily CSV raises ValueError (not raw ParserError)."""
        (temp_data_dir / "daily_data_2026-01-15.csv").write_text(
            'col1,col2\n1,"unclosed', encoding="utf-8"
        )
        with pytest.raises(ValueError, match="Daily data unreadable"):
            loader.load_daily_data()

    def test_get_latest_date_returns_date_string(self, loader, temp_data_dir):
        """get_latest_date returns date from most recent file by filename date."""
        df = pd.DataFrame({"symbol": ["A"], "close": [100.0], "change_percent": [0.0]})
        df.to_csv(temp_data_dir / "daily_data_2026-01-20.csv", index=False)
        df.to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)

        result = loader.get_latest_date()
        assert result == "2026-01-20"

    def test_get_latest_date_uses_filename_date_not_mtime(self, loader, temp_data_dir):
        """get_latest_date uses date in filename, not file mtime."""
        df = pd.DataFrame({"symbol": ["A"], "close": [100.0], "change_percent": [0.0]})
        newer_date_file = temp_data_dir / "daily_data_2026-01-20.csv"
        older_date_file = temp_data_dir / "daily_data_2026-01-15.csv"
        df.to_csv(newer_date_file, index=False)
        df.to_csv(older_date_file, index=False)
        # Make older-date file have newer mtime
        time.sleep(0.01)
        os.utime(older_date_file, (time.time(), time.time()))

        result = loader.get_latest_date()
        assert result == "2026-01-20"

    def test_get_available_dates_returns_sorted_list(self, loader, temp_data_dir):
        """get_available_dates returns sorted list of dates."""
        df = pd.DataFrame({"symbol": ["A"], "close": [100.0], "change_percent": [0.0]})
        df.to_csv(temp_data_dir / "daily_data_2026-01-10.csv", index=False)
        df.to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)

        result = loader.get_available_dates()
        assert len(result) == 2
        assert result == sorted(result, reverse=True)

    def test_load_daily_data_loads_by_filename_date_not_mtime(self, loader, temp_data_dir):
        """load_daily_data loads latest by date in filename, not mtime."""
        df_old = pd.DataFrame({"symbol": ["OLD"], "close": [50.0], "change_percent": [0.0]})
        df_new = pd.DataFrame({"symbol": ["NEW"], "close": [100.0], "change_percent": [0.0]})
        newer_file = temp_data_dir / "daily_data_2026-01-20.csv"
        older_file = temp_data_dir / "daily_data_2026-01-15.csv"
        df_new.to_csv(newer_file, index=False)
        df_old.to_csv(older_file, index=False)
        time.sleep(0.01)
        os.utime(older_file, (time.time(), time.time()))

        result = loader.load_daily_data()
        assert result.iloc[0]["symbol"] == "NEW"

    def test_compute_projection_accuracy_matches_actual(self, loader, temp_data_dir):
        """Reports exact-session error, direction, band, and calibration metrics."""
        pd.DataFrame({"symbol": ["AAPL"], "close": [100.0]}).to_csv(
            temp_data_dir / "daily_data_2026-01-05.csv", index=False
        )
        pd.DataFrame({"symbol": ["AAPL"], "close": [105.0]}).to_csv(
            temp_data_dir / "daily_data_2026-01-12.csv", index=False
        )
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "current_price": [100.0],
                "target_low": [104.0],
                "target_mid": [110.0],
                "target_high": [112.0],
                "recommendation": ["BUY"],
                "confidence": [70],
            }
        ).to_csv(temp_data_dir / "projections_2026-01-05.csv", index=False)

        out = loader.compute_projection_accuracy(days=90)
        summary = out["summary"]

        assert summary["calendar"] == "XNYS"
        assert summary["horizonSessions"] == 5
        assert summary["sampleCount"] == 1
        assert summary["meanAbsErrorPct"] == 4.762
        assert summary["directionalAccuracyPct"] == 100.0
        assert summary["bandCoveragePct"] == 100.0
        assert summary["calibrationGapPct"] == -30.0
        assert summary["evaluationCoveragePct"] == 100.0
        assert out["samples"][0]["targetDate"] == "2026-01-12"
        assert out["samples"][0]["actualDate"] == "2026-01-12"
        assert out["samples"][0]["symbol"] == "AAPL"
        assert "BUY" in summary["byRecommendation"]
        assert "70-79" in summary["byConfidenceBand"]

    def test_compute_projection_accuracy_does_not_roll_missing_close_forward(
        self, loader, temp_data_dir
    ):
        """A later close cannot turn an exact-session gap into a variable-horizon score."""
        pd.DataFrame({"symbol": ["AAPL"], "close": [100.0]}).to_csv(
            temp_data_dir / "daily_data_2026-01-05.csv", index=False
        )
        pd.DataFrame({"symbol": ["AAPL"], "close": [108.0]}).to_csv(
            temp_data_dir / "daily_data_2026-01-13.csv", index=False
        )
        pd.DataFrame(
            {"symbol": ["AAPL"], "current_price": [100.0], "target_mid": [110.0]}
        ).to_csv(temp_data_dir / "projections_2026-01-05.csv", index=False)

        out = loader.compute_projection_accuracy(days=90)

        assert out["summary"]["sampleCount"] == 0
        assert out["summary"]["missingActualCount"] == 1
        assert out["summary"]["evaluationCoveragePct"] == 0.0
        assert out["samples"] == []

    def test_compute_projection_accuracy_counts_pending_and_invalid(
        self, loader, temp_data_dir
    ):
        """Unmatured and malformed projections remain visible in report coverage."""
        pd.DataFrame({"symbol": ["AAPL"], "close": [100.0]}).to_csv(
            temp_data_dir / "daily_data_2026-01-05.csv", index=False
        )
        pd.DataFrame(
            {
                "symbol": ["AAPL", "MSFT"],
                "target_mid": [120.0, "not-a-number"],
                "recommendation": ["BUY", "HOLD"],
            }
        ).to_csv(temp_data_dir / "projections_2026-01-05.csv", index=False)

        out = loader.compute_projection_accuracy(days=90)

        assert out["summary"]["projectionCount"] == 2
        assert out["summary"]["validProjectionCount"] == 1
        assert out["summary"]["pendingCount"] == 1
        assert out["summary"]["invalidCount"] == 1
        assert out["summary"]["sampleCount"] == 0

    def test_load_projections_raises_value_error_on_corrupt_csv(self, loader, temp_data_dir):
        """Unreadable projections CSV raises ValueError (not raw ParserError)."""
        (temp_data_dir / "projections_2026-01-15.csv").write_text(
            'col1,col2\n1,"unclosed', encoding="utf-8"
        )
        with pytest.raises(ValueError, match="Projections unreadable"):
            loader.load_projections()

    def test_compute_projection_accuracy_normalizes_padded_and_skips_sentinels(
        self, loader, temp_data_dir
    ):
        """Padded symbols match daily rows; None/NaN never become NONE/NAN samples."""
        pd.DataFrame(
            {
                "symbol": ["AAPL", "  msft  "],
                "close": [100.0, 200.0],
                "change_percent": [0.0, 0.0],
            }
        ).to_csv(temp_data_dir / "daily_data_2026-01-12.csv", index=False)
        pd.DataFrame(
            {
                "symbol": [" aapl ", None, float("nan"), "  ", "MSFT"],
                "target_mid": [110.0, 50.0, 60.0, 70.0, 210.0],
                "recommendation": ["BUY", "HOLD", "HOLD", "HOLD", "SELL"],
            }
        ).to_csv(temp_data_dir / "projections_2026-01-05.csv", index=False)
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "close": [95.0],
                "change_percent": [0.0],
            }
        ).to_csv(temp_data_dir / "daily_data_2026-01-05.csv", index=False)

        out = loader.compute_projection_accuracy(days=90)

        assert out["summary"]["sampleCount"] == 2
        symbols = {s["symbol"] for s in out["samples"]}
        assert symbols == {"AAPL", "MSFT"}
        assert "NONE" not in symbols
        assert "NAN" not in symbols
        by_sym = {s["symbol"]: s for s in out["samples"]}
        assert by_sym["AAPL"]["absErrorPct"] == 10.0
        assert by_sym["MSFT"]["absErrorPct"] == 5.0
        assert out["summary"]["invalidCount"] == 3

    def test_load_historical_data_matches_padded_symbols_and_skips_sentinels(
        self, loader, temp_data_dir
    ):
        """Historical lookup must normalize CSV symbols and reject blank/sentinel keys."""
        from datetime import date, timedelta

        recent = (date.today() - timedelta(days=1)).isoformat()
        pd.DataFrame(
            {
                "symbol": [" AAPL "],
                "close": [155.0],
                "change_percent": [0.5],
                "volume": [1_000],
            }
        ).to_csv(temp_data_dir / f"daily_data_{recent}.csv", index=False)
        pd.DataFrame(
            {
                "symbol": ["aapl"],
                "target_mid": [165.0],
                "confidence": [70],
                "recommendation": ["BUY"],
                "expected_change_percent": [3.0],
            }
        ).to_csv(temp_data_dir / f"projections_{recent}.csv", index=False)

        rows = loader.load_historical_data(" aapl ", days=7)
        assert len(rows) == 1
        assert rows[0]["date"] == recent
        assert rows[0]["close"] == 155.0
        assert rows[0]["projection"]["target_price"] == 165.0

        assert loader.load_historical_data(None, days=7) == []
        assert loader.load_historical_data(float("nan"), days=7) == []
        assert loader.load_historical_data("NONE", days=7) == []

    def test_get_latest_date_falls_back_when_only_weekends(self, loader, temp_data_dir):
        """If every file is a weekend date, still return the newest one."""
        df = pd.DataFrame({"symbol": ["A"], "close": [1.0], "change_percent": [0.0]})
        df.to_csv(temp_data_dir / "daily_data_2026-01-17.csv", index=False)
        df.to_csv(temp_data_dir / "daily_data_2026-01-18.csv", index=False)

        assert loader.get_latest_date() == "2026-01-18"

    def test_get_latest_date_skips_weekend_files(self, loader, temp_data_dir):
        """Prefer Friday over newer Saturday/Sunday filenames."""
        df = pd.DataFrame({"symbol": ["A"], "close": [1.0], "change_percent": [0.0]})
        df.to_csv(temp_data_dir / "daily_data_2026-01-16.csv", index=False)  # Fri
        df.to_csv(temp_data_dir / "daily_data_2026-01-17.csv", index=False)  # Sat
        df.to_csv(temp_data_dir / "daily_data_2026-01-18.csv", index=False)  # Sun

        assert loader.get_latest_date() == "2026-01-16"
        loaded = loader.load_daily_data()
        assert list(loaded["symbol"]) == ["A"]

    def test_get_most_recent_trading_day_weekend_rolls_to_friday(self, monkeypatch):
        """Saturday/Sunday map to the prior Friday."""
        from datetime import date
        import dashboard.backend.services.data_loader as dl

        class _Sat:
            @classmethod
            def now(cls):
                class _N:
                    @staticmethod
                    def date():
                        return date(2026, 1, 17)  # Saturday

                return _N()

        class _Sun:
            @classmethod
            def now(cls):
                class _N:
                    @staticmethod
                    def date():
                        return date(2026, 1, 18)  # Sunday

                return _N()

        monkeypatch.setattr(dl, "datetime", _Sat)
        assert dl.get_most_recent_trading_day() == "2026-01-16"
        monkeypatch.setattr(dl, "datetime", _Sun)
        assert dl.get_most_recent_trading_day() == "2026-01-16"

    def test_is_weekday_and_unparseable_dates(self):
        """Weekdays are open; weekends closed; unparseable dates stay kept."""
        from dashboard.backend.services.data_loader import _is_weekday

        assert _is_weekday("2026-01-16") is True  # Friday
        assert _is_weekday("2026-01-17") is False  # Saturday
        assert _is_weekday("2026-01-18") is False  # Sunday
        assert _is_weekday("not-a-date") is True

    def test_load_historical_data_merges_projection_and_skips_gaps(
        self, loader, temp_data_dir, monkeypatch
    ):
        """Attach projection fields when present; skip missing/broken dates."""
        from datetime import date
        import dashboard.backend.services.data_loader as dl

        class _Now:
            @classmethod
            def now(cls):
                class _N:
                    @staticmethod
                    def date():
                        return date(2026, 1, 20)

                    def __sub__(self, other):
                        return date(2026, 1, 20) - other

                return _N()

        monkeypatch.setattr(dl, "datetime", _Now)

        pd.DataFrame(
            {"symbol": ["AAPL"], "close": [100.0], "change_percent": [0.0]}
        ).to_csv(temp_data_dir / "daily_data_2026-01-16.csv", index=False)
        pd.DataFrame(
            {"symbol": ["MSFT"], "close": [200.0], "change_percent": [0.0]}
        ).to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)
        # Corrupt / unreadable daily file should be skipped
        (temp_data_dir / "daily_data_2026-01-14.csv").write_text("not,csv\n")
        pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "target_mid": [110.0],
                "confidence": [70],
                "recommendation": ["BUY"],
                "expected_change_percent": [5.0],
            }
        ).to_csv(temp_data_dir / "projections_2026-01-16.csv", index=False)

        rows = loader.load_historical_data("AAPL", days=30)
        assert len(rows) == 1
        assert rows[0]["date"] == "2026-01-16"
        assert rows[0]["projection"]["target_price"] == 110.0
        assert rows[0]["projection"]["recommendation"] == "BUY"

    def test_needs_fetch_for_latest_trading_day(self, loader, temp_data_dir, monkeypatch):
        """True when latest trading day is missing; false when present."""
        from datetime import date
        import dashboard.backend.services.data_loader as dl

        class _Fri:
            @classmethod
            def now(cls):
                class _N:
                    @staticmethod
                    def date():
                        return date(2026, 1, 16)

                return _N()

        monkeypatch.setattr(dl, "datetime", _Fri)
        df = pd.DataFrame({"symbol": ["A"], "close": [1.0], "change_percent": [0.0]})
        df.to_csv(temp_data_dir / "daily_data_2026-01-15.csv", index=False)
        assert loader.needs_fetch_for_latest_trading_day() is True

        df.to_csv(temp_data_dir / "daily_data_2026-01-16.csv", index=False)
        assert loader.needs_fetch_for_latest_trading_day() is False

"""Malformed market-data filenames must not become the latest trading day."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from dashboard.backend.services.data_loader import DataLoader, _is_iso_date


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def loader(data_dir: Path) -> DataLoader:
    return DataLoader(data_dir=data_dir)


def _write_daily(data_dir: Path, suffix: str) -> Path:
    path = data_dir / f"daily_data_{suffix}.csv"
    pd.DataFrame(
        {"symbol": ["AAPL"], "close": [100.0], "change_percent": [1.0]}
    ).to_csv(path, index=False)
    return path


def test_is_iso_date_accepts_strict_calendar_dates() -> None:
    assert _is_iso_date("2026-01-15") is True
    assert _is_iso_date("2026-02-30") is False
    assert _is_iso_date("zzzz") is False
    assert _is_iso_date("2026-1-15") is False
    assert _is_iso_date("not-a-date") is False


def test_get_available_dates_ignores_malformed_suffixes(
    loader: DataLoader, data_dir: Path
) -> None:
    _write_daily(data_dir, "2026-01-15")
    _write_daily(data_dir, "zzzz")
    _write_daily(data_dir, "tmp")
    _write_daily(data_dir, "2026-01-15.bak")
    (data_dir / "daily_data_.csv").write_text("symbol,close\nA,1\n", encoding="utf-8")

    assert loader.get_available_dates() == ["2026-01-15"]


def test_get_latest_date_prefers_valid_iso_over_lexicographic_garbage(
    loader: DataLoader, data_dir: Path
) -> None:
    _write_daily(data_dir, "2026-01-15")  # Thursday
    _write_daily(data_dir, "zzzz")  # would sort above ISO dates lexicographically

    assert loader.get_latest_date() == "2026-01-15"


def test_load_daily_data_default_ignores_malformed_competitors(
    loader: DataLoader, data_dir: Path
) -> None:
    _write_daily(data_dir, "2026-01-14")  # Wednesday
    garbage = _write_daily(data_dir, "zzzz")
    garbage.write_text("symbol,close,change_percent\nGARBAGE,1,0\n", encoding="utf-8")

    frame = loader.load_daily_data()
    assert list(frame["symbol"]) == ["AAPL"]


def test_get_latest_file_returns_none_when_only_malformed_dates(
    loader: DataLoader, data_dir: Path
) -> None:
    _write_daily(data_dir, "zzzz")
    _write_daily(data_dir, "partial")

    assert loader._get_latest_file("daily_data_*.csv", sort_by_date=True) is None
    assert loader.get_available_dates() == []
    assert loader.get_latest_date() is None


def test_get_available_dates_maps_glob_oserror_to_valueerror(loader: DataLoader) -> None:
    """Unreadable data/ must become ValueError so history/overview APIs return 404."""
    from unittest.mock import MagicMock

    fake_dir = MagicMock()
    fake_dir.glob.side_effect = OSError("permission denied")
    loader.data_dir = fake_dir
    with pytest.raises(ValueError, match="unreadable"):
        loader.get_available_dates()

"""ISO date helpers and market_bars date listing edge cases."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from dashboard.backend.services.data_loader import DataLoader, _is_iso_date
from tests.helpers.market_bars import seed_simple_bars


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    return tmp_path


@pytest.fixture
def loader(data_dir: Path) -> DataLoader:
    return DataLoader(data_dir=data_dir)


def test_is_iso_date_accepts_strict_calendar_dates() -> None:
    assert _is_iso_date("2026-01-15") is True
    assert _is_iso_date("2026-02-30") is False
    assert _is_iso_date("zzzz") is False
    assert _is_iso_date("2026-1-15") is False
    assert _is_iso_date("not-a-date") is False


def test_get_available_dates_returns_seeded_iso_dates(
    loader: DataLoader, data_dir: Path
) -> None:
    seed_simple_bars(data_dir, "2026-01-15")
    assert loader.get_available_dates() == ["2026-01-15"]


def test_get_latest_date_returns_newest_seeded_date(
    loader: DataLoader, data_dir: Path
) -> None:
    seed_simple_bars(data_dir, "2026-01-15")  # Thursday
    seed_simple_bars(data_dir, "2026-01-14")  # Wednesday

    assert loader.get_latest_date() == "2026-01-15"


def test_load_daily_data_default_uses_newest_weekday(
    loader: DataLoader, data_dir: Path
) -> None:
    seed_simple_bars(data_dir, "2026-01-14", symbol="OLDER", close=50.0)
    seed_simple_bars(data_dir, "2026-01-15", symbol="NEWER", close=100.0)

    frame = loader.load_daily_data()
    assert list(frame["symbol"]) == ["NEWER"]


def test_empty_store_has_no_available_dates(
    loader: DataLoader, data_dir: Path
) -> None:
    assert loader.get_available_dates() == []
    assert loader.get_latest_date() is None


def test_get_available_dates_maps_list_oserror_to_valueerror(
    loader: DataLoader,
) -> None:
    """Unreadable market_bars must become ValueError so history/overview APIs return 404."""
    with patch(
        "src.storage.market_bars.list_market_bar_dates",
        side_effect=OSError("permission denied"),
    ):
        with pytest.raises(ValueError, match="unreadable"):
            loader.get_available_dates()

"""Latest-file lookup must map data-dir I/O errors to ValueError (API 404)."""

from unittest.mock import MagicMock

import pytest

from dashboard.backend.services.data_loader import DataLoader


@pytest.fixture
def loader(tmp_path) -> DataLoader:
    return DataLoader(data_dir=tmp_path)


def test_get_latest_file_maps_glob_oserror_to_valueerror(loader: DataLoader) -> None:
    fake_dir = MagicMock()
    fake_dir.glob.side_effect = OSError("permission denied")
    loader.data_dir = fake_dir
    with pytest.raises(ValueError, match="unreadable"):
        loader._get_latest_file("daily_data_*.csv", sort_by_date=True)


def test_load_daily_data_maps_glob_oserror_to_valueerror(loader: DataLoader) -> None:
    fake_dir = MagicMock()
    fake_dir.glob.side_effect = OSError("permission denied")
    loader.data_dir = fake_dir
    with pytest.raises(ValueError, match="unreadable"):
        loader.load_daily_data()


def test_get_latest_file_maps_stat_oserror_to_valueerror(loader: DataLoader) -> None:
    fake_file = MagicMock()
    fake_file.stat.side_effect = OSError("stat failed")
    fake_dir = MagicMock()
    fake_dir.glob.return_value = [fake_file]
    loader.data_dir = fake_dir
    with pytest.raises(ValueError, match="unreadable"):
        loader._get_latest_file("daily_data_*.csv", sort_by_date=False)

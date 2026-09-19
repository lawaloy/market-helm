"""Latest-file / market_bars I/O errors must map to ValueError (API 404)."""

from unittest.mock import patch

import pytest

from dashboard.backend.services.data_loader import DataLoader


@pytest.fixture
def loader(tmp_path, monkeypatch) -> DataLoader:
    monkeypatch.delenv("MARKET_HELM_DATABASE_URL", raising=False)
    return DataLoader(data_dir=tmp_path)


def test_load_daily_data_maps_market_bars_oserror_to_valueerror(
    loader: DataLoader,
) -> None:
    with patch(
        "src.storage.market_bars.list_market_bar_dates",
        side_effect=OSError("permission denied"),
    ):
        with pytest.raises(ValueError, match="unreadable"):
            loader.load_daily_data()


def test_load_projections_maps_store_oserror_to_valueerror(loader: DataLoader) -> None:
    with patch(
        "src.storage.projections_store.list_projection_dates",
        side_effect=OSError("permission denied"),
    ):
        with pytest.raises(ValueError, match="unreadable"):
            loader.load_projections()


def test_load_summary_maps_store_oserror_to_valueerror(loader: DataLoader) -> None:
    with patch(
        "src.storage.projections_store.list_summary_dates",
        side_effect=OSError("permission denied"),
    ):
        with pytest.raises(ValueError, match="unreadable"):
            loader.load_summary()

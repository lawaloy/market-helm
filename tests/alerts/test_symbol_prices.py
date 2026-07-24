"""Tests for symbol price resolution."""

from unittest.mock import MagicMock, patch

import pandas as pd

from src.alerts.symbol_prices import prices_from_saved_daily_data, resolve_symbol_prices


@patch("dashboard.backend.services.data_loader.get_data_loader")
def test_prices_from_saved_daily_data(mock_get_loader):
    loader = MagicMock()
    loader.load_daily_data.return_value = pd.DataFrame(
        [{"symbol": "AAPL", "close": 180.5}, {"symbol": "GOOGL", "close": 170.25}]
    )
    mock_get_loader.return_value = loader

    assert prices_from_saved_daily_data() == {"AAPL": 180.5, "GOOGL": 170.25}


@patch("src.services.data_fetcher.StockDataFetcher")
@patch("src.alerts.symbol_prices.prices_from_saved_daily_data", return_value={"AAPL": 180.5})
def test_resolve_symbol_prices_fetches_missing(_mock_saved, mock_fetcher_cls):
    fetcher = MagicMock()
    fetcher.fetch_symbol_data.return_value = {"symbol": "NVDA", "close": 900.0}
    mock_fetcher_cls.return_value = fetcher

    prices = resolve_symbol_prices(["AAPL", "NVDA"], fetch_missing=True)

    assert prices == {"AAPL": 180.5, "NVDA": 900.0}
    fetcher.fetch_symbol_data.assert_called_once_with("NVDA")


@patch(
    "src.alerts.symbol_prices.prices_from_saved_daily_data",
    return_value={"AAPL": 180.5, "MSFT": 400.0},
)
def test_resolve_symbol_prices_skips_blank_and_dedupes_case(_mock_saved):
    """Quote pickers must ignore empty tokens and treat ticker case as identical."""
    prices = resolve_symbol_prices(
        ["", "  ", "aapl", "AAPL", "msft"],
        fetch_missing=False,
    )

    assert prices == {"AAPL": 180.5, "MSFT": 400.0}


def test_resolve_symbol_prices_returns_empty_for_blank_only_input():
    assert resolve_symbol_prices(["", "   "], fetch_missing=False) == {}

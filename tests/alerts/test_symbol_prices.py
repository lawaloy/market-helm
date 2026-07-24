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


@patch("dashboard.backend.services.data_loader.get_data_loader")
def test_prices_from_saved_daily_data_skips_invalid_rows_and_loader_errors(mock_get_loader):
    loader = MagicMock()
    loader.load_daily_data.return_value = pd.DataFrame(
        [
            {"symbol": "AAPL", "close": 180.5},
            {"symbol": "", "close": 12.0},
            {"symbol": "BAD", "close": "n/a"},
        ]
    )
    mock_get_loader.return_value = loader
    assert prices_from_saved_daily_data() == {"AAPL": 180.5}

    loader.load_daily_data.return_value = pd.DataFrame(
        [{"symbol": "GOOG", "price": 140.0}]
    )
    assert prices_from_saved_daily_data() == {"GOOG": 140.0}

    mock_get_loader.side_effect = ValueError("No daily data files found")
    assert prices_from_saved_daily_data() == {}


@patch("src.services.data_fetcher.StockDataFetcher", side_effect=ValueError("API key required"))
@patch(
    "src.alerts.symbol_prices.prices_from_saved_daily_data",
    return_value={"AAPL": 180.5},
)
def test_resolve_symbol_prices_keeps_saved_when_live_fetcher_unavailable(
    _mock_saved, _mock_fetcher_cls
):
    prices = resolve_symbol_prices(["AAPL", "NVDA"], fetch_missing=True)
    assert prices == {"AAPL": 180.5}


@patch("src.services.data_fetcher.StockDataFetcher")
@patch("src.alerts.symbol_prices.prices_from_saved_daily_data", return_value={})
def test_resolve_symbol_prices_caps_live_fetches_and_skips_bad_quotes(
    _mock_saved, mock_fetcher_cls
):
    fetcher = MagicMock()

    def fetch_symbol_data(symbol: str):
        if symbol == "OK1":
            return {"symbol": symbol, "close": 10.0}
        if symbol == "BAD":
            raise RuntimeError("quote failed")
        if symbol == "EMPTY":
            return None
        if symbol == "NAN":
            return {"symbol": symbol, "close": "x"}
        return {"symbol": symbol, "close": 1.0}

    fetcher.fetch_symbol_data.side_effect = fetch_symbol_data
    mock_fetcher_cls.return_value = fetcher

    # 16 missing symbols: only the first 15 should be submitted for live fetch.
    symbols = [f"S{i}" for i in range(13)] + ["OK1", "BAD", "EMPTY", "NAN"]
    prices = resolve_symbol_prices(symbols, fetch_missing=True)

    assert prices == {"OK1": 10.0, **{f"S{i}": 1.0 for i in range(13)}}
    assert fetcher.fetch_symbol_data.call_count == 15
    fetched = {call.args[0] for call in fetcher.fetch_symbol_data.call_args_list}
    assert fetched == {f"S{i}" for i in range(13)} | {"OK1", "BAD"}
    assert "EMPTY" not in fetched
    assert "NAN" not in fetched

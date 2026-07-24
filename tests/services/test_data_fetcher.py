"""Tests for StockDataFetcher retry and index aggregation edges."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.data_fetcher import StockDataFetcher


def test_stock_data_fetcher_requires_api_client(monkeypatch):
    monkeypatch.setattr(
        "src.services.data_fetcher.FinnhubClient",
        MagicMock(side_effect=ValueError("API key required")),
    )

    with pytest.raises(ValueError, match="API key required"):
        StockDataFetcher()


def test_fetch_symbol_data_returns_payload_on_success():
    client = MagicMock()
    client.get_stock_data.return_value = {"symbol": "AAPL", "close": 190.0}
    fetcher = StockDataFetcher(api_client=client, include_profile=False)

    assert fetcher.fetch_symbol_data("AAPL") == {"symbol": "AAPL", "close": 190.0}
    client.get_stock_data.assert_called_once_with("AAPL", include_profile=False)


def test_fetch_symbol_data_retries_then_returns_none(monkeypatch):
    client = MagicMock()
    client.get_stock_data.side_effect = RuntimeError("rate limited")
    fetcher = StockDataFetcher(api_client=client, include_profile=False)
    sleeps: list[float] = []
    monkeypatch.setattr("src.services.data_fetcher.time.sleep", sleeps.append)

    assert fetcher.fetch_symbol_data("NVDA", max_retries=3) is None
    assert client.get_stock_data.call_count == 3
    assert sleeps == [0.5, 1.0]


@patch("src.services.data_fetcher.get_indices_to_track", return_value=["S&P 500"])
@patch("src.services.data_fetcher.IndexFetcher")
def test_fetch_all_indices_caps_symbols_and_skips_empty(
    mock_index_fetcher_cls, _mock_indices, monkeypatch
):
    index_fetcher = MagicMock()
    index_fetcher.get_index_symbols.return_value = [f"S{i}" for i in range(150)]
    mock_index_fetcher_cls.return_value = index_fetcher

    client = MagicMock()
    fetcher = StockDataFetcher(api_client=client, include_profile=False)

    def fake_fetch(symbol: str, **_kwargs):
        if symbol == "S0":
            return {"symbol": symbol, "close": 1.0}
        return None

    monkeypatch.setattr(fetcher, "fetch_symbol_data", fake_fetch)
    monkeypatch.setenv("STOCK_FETCH_MAX_WORKERS", "1")
    monkeypatch.setattr("src.services.data_fetcher.time.sleep", lambda _seconds: None)

    result = fetcher.fetch_all_indices(use_screener=False)

    assert list(result.keys()) == ["S&P 500"]
    assert result["S&P 500"] == [{"symbol": "S0", "close": 1.0, "index_name": "S&P 500"}]


@patch("src.services.data_fetcher.get_indices_to_track", return_value=["NASDAQ-100"])
@patch("src.services.data_fetcher.IndexFetcher")
def test_fetch_all_indices_continues_when_index_has_no_symbols(
    mock_index_fetcher_cls, _mock_indices
):
    index_fetcher = MagicMock()
    index_fetcher.get_index_symbols.return_value = []
    mock_index_fetcher_cls.return_value = index_fetcher
    fetcher = StockDataFetcher(api_client=MagicMock(), include_profile=False)

    assert fetcher.fetch_all_indices(use_screener=False) == {}

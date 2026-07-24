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


@patch("src.services.data_fetcher.get_indices_to_track", return_value=["S&P 500"])
@patch("src.services.data_fetcher.IndexFetcher")
def test_fetch_all_indices_uses_default_filters_when_json_corrupt(
    mock_index_fetcher_cls, _mock_indices, monkeypatch
):
    """Corrupt filters.json must soft-fail to StockScreener defaults (None)."""
    import json
    from pathlib import Path
    from io import StringIO

    symbols = [f"S{i}" for i in range(25)]
    index_fetcher = MagicMock()
    index_fetcher.get_index_symbols.return_value = symbols
    mock_index_fetcher_cls.return_value = index_fetcher

    filters_suffix = str(Path("config") / "filters.json")
    real_exists = Path.exists
    real_open = open

    def exists_with_filters(self):
        if str(self).endswith(filters_suffix) or self.name == "filters.json":
            return True
        return real_exists(self)

    def open_corrupt_filters(file, *args, **kwargs):
        path_str = str(file)
        if path_str.endswith(filters_suffix) or path_str.endswith("filters.json"):
            return StringIO("{not-valid-json")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(Path, "exists", exists_with_filters)
    monkeypatch.setattr("builtins.open", open_corrupt_filters)

    screener = MagicMock()
    screener.get_qualified_symbols.return_value = ["S0", "S1"]
    screener_cls = MagicMock(return_value=screener)

    fetcher = StockDataFetcher(api_client=MagicMock(), include_profile=False)
    monkeypatch.setattr(
        fetcher, "fetch_symbol_data", lambda symbol, **_k: {"symbol": symbol, "close": 1.0}
    )
    monkeypatch.setenv("STOCK_FETCH_MAX_WORKERS", "1")
    monkeypatch.setattr("src.services.data_fetcher.time.sleep", lambda _seconds: None)

    with patch("src.services.stock_screener.StockScreener", screener_cls):
        result = fetcher.fetch_all_indices(use_screener=True)

    screener_cls.assert_called_once()
    assert screener_cls.call_args.args[0] is None
    assert sorted(row["symbol"] for row in result["S&P 500"]) == ["S0", "S1"]


@patch("src.services.data_fetcher.get_indices_to_track", return_value=["S&P 500"])
@patch("src.services.data_fetcher.IndexFetcher")
def test_fetch_all_indices_continues_when_symbol_fetch_raises(
    mock_index_fetcher_cls, _mock_indices, monkeypatch
):
    """One symbol future exception must not abort the rest of the index batch."""
    index_fetcher = MagicMock()
    index_fetcher.get_index_symbols.return_value = ["GOOD", "BAD", "OK"]
    mock_index_fetcher_cls.return_value = index_fetcher

    fetcher = StockDataFetcher(api_client=MagicMock(), include_profile=False)

    def fake_fetch(symbol: str, **_kwargs):
        if symbol == "BAD":
            raise RuntimeError("thread boom")
        return {"symbol": symbol, "close": 10.0}

    monkeypatch.setattr(fetcher, "fetch_symbol_data", fake_fetch)
    monkeypatch.setenv("STOCK_FETCH_MAX_WORKERS", "1")
    monkeypatch.setattr("src.services.data_fetcher.time.sleep", lambda _seconds: None)

    result = fetcher.fetch_all_indices(use_screener=False)

    symbols = sorted(row["symbol"] for row in result["S&P 500"])
    assert symbols == ["GOOD", "OK"]
    assert all(row["index_name"] == "S&P 500" for row in result["S&P 500"])

"""Non-positive / dirty max_symbols_per_index must not fan out full-index fetches."""

from unittest.mock import MagicMock, patch

from src.services.data_fetcher import StockDataFetcher


@patch("src.services.data_fetcher.get_indices_to_track", return_value=["S&P 500"])
@patch("src.services.data_fetcher.IndexFetcher")
def test_fetch_all_indices_skips_when_max_symbols_non_positive(
    mock_index_fetcher_cls, _mock_indices, monkeypatch
):
    """0 used to disable the limit; negatives reverse-sliced the symbol list."""
    index_fetcher = MagicMock()
    index_fetcher.get_index_symbols.return_value = [f"S{i}" for i in range(20)]
    mock_index_fetcher_cls.return_value = index_fetcher

    fetcher = StockDataFetcher(api_client=MagicMock(), include_profile=False)
    fetched: list[str] = []

    def fake_fetch(symbol: str, **_kwargs):
        fetched.append(symbol)
        return {"symbol": symbol, "close": 1.0}

    monkeypatch.setattr(fetcher, "fetch_symbol_data", fake_fetch)
    monkeypatch.setenv("STOCK_FETCH_MAX_WORKERS", "1")
    monkeypatch.setattr("src.services.data_fetcher.time.sleep", lambda _seconds: None)

    for bad_limit in (0, -3):
        fetched.clear()
        result = fetcher.fetch_all_indices(
            use_screener=False, max_symbols_per_index=bad_limit
        )
        assert fetched == []
        assert result == {}


@patch("src.services.data_fetcher.get_indices_to_track", return_value=["S&P 500"])
@patch("src.services.data_fetcher.IndexFetcher")
def test_fetch_all_indices_skips_when_max_symbols_unparseable(
    mock_index_fetcher_cls, _mock_indices, monkeypatch
):
    index_fetcher = MagicMock()
    index_fetcher.get_index_symbols.return_value = [f"S{i}" for i in range(10)]
    mock_index_fetcher_cls.return_value = index_fetcher

    fetcher = StockDataFetcher(api_client=MagicMock(), include_profile=False)
    fetched: list[str] = []
    monkeypatch.setattr(
        fetcher,
        "fetch_symbol_data",
        lambda symbol, **_kwargs: fetched.append(symbol) or {"symbol": symbol},
    )
    monkeypatch.setenv("STOCK_FETCH_MAX_WORKERS", "1")
    monkeypatch.setattr("src.services.data_fetcher.time.sleep", lambda _seconds: None)

    result = fetcher.fetch_all_indices(
        use_screener=False, max_symbols_per_index=float("nan")
    )
    assert fetched == []
    assert result == {}

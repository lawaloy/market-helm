"""Live watch-quote backfill must honor the shared Finnhub fetch budget."""

from unittest.mock import MagicMock, patch

from src.alerts.alert_runner import _MAX_LIVE_WATCH_FETCH, _fetch_missing_watch_quotes


@patch("src.services.data_fetcher.StockDataFetcher")
def test_fetch_missing_watch_quotes_caps_live_fetches(mock_fetcher_cls, caplog) -> None:
    """More missing watches than the budget → only the first N hit Finnhub."""
    fetcher = MagicMock()
    fetcher.fetch_symbol_data.side_effect = lambda symbol: {
        "symbol": symbol,
        "close": 100.0,
    }
    mock_fetcher_cls.return_value = fetcher

    watch_symbols = [f"SYM{i:02d}" for i in range(_MAX_LIVE_WATCH_FETCH + 10)]

    with caplog.at_level("WARNING"):
        enriched = _fetch_missing_watch_quotes([], watch_symbols)

    assert len(enriched) == _MAX_LIVE_WATCH_FETCH
    assert [row["symbol"] for row in enriched] == watch_symbols[:_MAX_LIVE_WATCH_FETCH]
    assert fetcher.fetch_symbol_data.call_count == _MAX_LIVE_WATCH_FETCH
    assert [c.args[0] for c in fetcher.fetch_symbol_data.call_args_list] == (
        watch_symbols[:_MAX_LIVE_WATCH_FETCH]
    )
    assert f"Capping live watch quote fetches from {len(watch_symbols)}" in caplog.text


@patch("src.services.data_fetcher.StockDataFetcher")
def test_fetch_missing_watch_quotes_cap_counts_only_missing(
    mock_fetcher_cls,
) -> None:
    """Symbols already in saved daily data do not consume the live budget."""
    fetcher = MagicMock()
    fetcher.fetch_symbol_data.side_effect = lambda symbol: {
        "symbol": symbol,
        "close": 50.0,
    }
    mock_fetcher_cls.return_value = fetcher

    present = [{"symbol": f"HAVE{i}", "close": 1.0} for i in range(20)]
    missing = [f"NEED{i:02d}" for i in range(5)]
    watches = [row["symbol"] for row in present] + missing

    enriched = _fetch_missing_watch_quotes(present, watches)

    assert fetcher.fetch_symbol_data.call_count == 5
    assert [c.args[0] for c in fetcher.fetch_symbol_data.call_args_list] == missing
    assert enriched[-5:] == [{"symbol": s, "close": 50.0} for s in missing]


@patch("src.services.data_fetcher.StockDataFetcher")
def test_fetch_missing_watch_quotes_dedupes_padded_duplicates_before_finnhub(
    mock_fetcher_cls,
) -> None:
    """Duplicate or padded watches must not extra-hit Finnhub.

    File-mode evaluate and hosted orchestrator ticks call this helper with the
    watch list. Without normalize+dedupe, ``AAPL`` plus `` aapl `` would hit
    Finnhub twice on every check cycle.
    """
    fetcher = MagicMock()
    fetcher.fetch_symbol_data.side_effect = lambda symbol: {
        "symbol": symbol,
        "close": 100.0,
    }
    mock_fetcher_cls.return_value = fetcher

    enriched = _fetch_missing_watch_quotes(
        [],
        [" aapl ", "AAPL", "AAPL", "msft", "  ", "NAN", "MSFT"],
    )

    assert [c.args[0] for c in fetcher.fetch_symbol_data.call_args_list] == [
        "AAPL",
        "MSFT",
    ]
    assert fetcher.fetch_symbol_data.call_count == 2
    assert [row["symbol"] for row in enriched] == ["AAPL", "MSFT"]
    mock_fetcher_cls.assert_called_once_with(include_profile=False)


@patch("src.services.data_fetcher.StockDataFetcher")
def test_fetch_missing_watch_quotes_at_budget_does_not_warn(
    mock_fetcher_cls, caplog
) -> None:
    fetcher = MagicMock()
    fetcher.fetch_symbol_data.side_effect = lambda symbol: {
        "symbol": symbol,
        "close": 10.0,
    }
    mock_fetcher_cls.return_value = fetcher
    watches = [f"T{i}" for i in range(_MAX_LIVE_WATCH_FETCH)]

    with caplog.at_level("WARNING"):
        enriched = _fetch_missing_watch_quotes([], watches)

    assert len(enriched) == _MAX_LIVE_WATCH_FETCH
    assert "Capping live watch quote fetches" not in caplog.text

"""Tests for alert evaluation against saved daily data."""

from unittest.mock import MagicMock, call, patch

import pandas as pd

from src.alerts.alert_paths import get_enabled_watch_symbols
from src.alerts.alert_runner import (
    _fetch_missing_watch_quotes,
    _stocks_from_daily_df,
    evaluate_alerts_from_latest_data,
)


@patch("src.alerts.alert_runner.AlertEngine")
@patch("src.alerts.alert_runner.get_enabled_watch_symbols", return_value=[])
@patch("dashboard.backend.services.data_loader.get_data_loader")
def test_evaluate_alerts_from_latest_data(mock_get_loader, _mock_watch_symbols, mock_engine_cls):
    loader = MagicMock()
    loader.get_latest_date.return_value = "2026-05-20"
    loader.load_daily_data.return_value = pd.DataFrame(
        [{"symbol": "AAPL", "close": 180.0}, {"symbol": "msft", "close": 420.0}]
    )
    mock_get_loader.return_value = loader

    engine = MagicMock()
    engine.evaluate.return_value = [{"id": "aapl_drop", "symbol": "AAPL"}]
    mock_engine_cls.from_config.return_value = engine

    result = evaluate_alerts_from_latest_data(fetch_missing_quotes=False)

    assert result["triggered"] == 1
    assert result["last_data_date"] == "2026-05-20"
    engine.evaluate.assert_called_once()
    stocks = engine.evaluate.call_args[0][0]
    assert stocks == [{"symbol": "AAPL", "close": 180.0}, {"symbol": "MSFT", "close": 420.0}]


@patch("src.alerts.alert_runner._fetch_missing_watch_quotes")
@patch("src.alerts.alert_runner.AlertEngine")
@patch("src.alerts.alert_runner.get_enabled_watch_symbols", return_value=["NVDA"])
@patch("dashboard.backend.services.data_loader.get_data_loader")
def test_evaluate_alerts_fetches_missing_watch_symbols(
    mock_get_loader, _mock_watch_symbols, mock_engine_cls, mock_fetch_missing
):
    loader = MagicMock()
    loader.get_latest_date.return_value = "2026-05-20"
    loader.load_daily_data.return_value = pd.DataFrame([{"symbol": "GOOGL", "close": 170.0}])
    mock_get_loader.return_value = loader
    mock_fetch_missing.side_effect = lambda stocks, _symbols: stocks + [
        {"symbol": "NVDA", "close": 900.0}
    ]

    engine = MagicMock()
    engine.evaluate.return_value = []
    mock_engine_cls.from_config.return_value = engine

    evaluate_alerts_from_latest_data()

    mock_fetch_missing.assert_called_once()
    stocks = engine.evaluate.call_args[0][0]
    assert stocks[-1] == {"symbol": "NVDA", "close": 900.0}


@patch("src.services.data_fetcher.StockDataFetcher")
def test_fetch_missing_watch_quotes_skips_present_symbols_and_recovers_from_failures(
    mock_fetcher_cls, caplog
):
    """Live backfill should enrich only missing symbols and tolerate partial API failures."""
    fetcher = MagicMock()

    def fetch_symbol(symbol):
        if symbol == "NVDA":
            return {"symbol": "NVDA", "price": 900.0}
        if symbol == "MSFT":
            raise RuntimeError("api timeout")
        if symbol == "TSLA":
            return {}
        if symbol == "AMD":
            return {"symbol": "AMD", "close": None}
        raise AssertionError(f"unexpected fetch for {symbol}")

    fetcher.fetch_symbol_data.side_effect = fetch_symbol
    mock_fetcher_cls.return_value = fetcher
    stocks = [{"symbol": "AAPL", "close": 180.0}]

    with caplog.at_level("WARNING"):
        enriched = _fetch_missing_watch_quotes(stocks, ["AAPL", "NVDA", "MSFT", "TSLA", "AMD"])

    assert enriched == [
        {"symbol": "AAPL", "close": 180.0},
        {"symbol": "NVDA", "close": 900.0},
    ]
    mock_fetcher_cls.assert_called_once_with(include_profile=False)
    assert fetcher.fetch_symbol_data.call_args_list == [
        call("NVDA"),
        call("MSFT"),
        call("TSLA"),
        call("AMD"),
    ]
    assert "Failed to fetch quote for watch symbol MSFT" in caplog.text


@patch("src.services.data_fetcher.StockDataFetcher")
def test_fetch_missing_watch_quotes_does_not_initialize_fetcher_when_all_symbols_present(
    mock_fetcher_cls,
):
    stocks = [{"symbol": "aapl", "close": 180.0}]

    enriched = _fetch_missing_watch_quotes(stocks, ["AAPL"])

    assert enriched is stocks
    mock_fetcher_cls.assert_not_called()


@patch("src.services.data_fetcher.StockDataFetcher")
def test_fetch_missing_watch_quotes_skips_invalid_live_prices(mock_fetcher_cls, caplog):
    fetcher = MagicMock()

    def fetch_symbol(symbol):
        if symbol == "NVDA":
            return {"symbol": symbol, "close": "not-a-price"}
        return {"symbol": symbol, "price": "410.25"}

    fetcher.fetch_symbol_data.side_effect = fetch_symbol
    mock_fetcher_cls.return_value = fetcher

    with caplog.at_level("WARNING"):
        enriched = _fetch_missing_watch_quotes(
            [{"symbol": "AAPL", "close": 180.0}],
            ["NVDA", "MSFT"],
        )

    assert enriched == [
        {"symbol": "AAPL", "close": 180.0},
        {"symbol": "MSFT", "close": 410.25},
    ]
    assert "Skipping invalid quote for watch symbol NVDA" in caplog.text
    assert fetcher.fetch_symbol_data.call_count == 2


@patch("src.services.data_fetcher.StockDataFetcher")
def test_fetch_missing_watch_quotes_skips_non_finite_live_prices(mock_fetcher_cls, caplog):
    """NaN/inf live closes must not enter alert evaluation stocks."""
    fetcher = MagicMock()

    def fetch_symbol(symbol):
        if symbol == "BAD1":
            return {"symbol": symbol, "close": float("nan")}
        if symbol == "BAD2":
            return {"symbol": symbol, "price": float("inf")}
        return {"symbol": symbol, "close": 410.25}

    fetcher.fetch_symbol_data.side_effect = fetch_symbol
    mock_fetcher_cls.return_value = fetcher

    with caplog.at_level("WARNING"):
        enriched = _fetch_missing_watch_quotes(
            [{"symbol": "AAPL", "close": 180.0}],
            ["BAD1", "BAD2", "MSFT", "nan", "  "],
        )

    assert enriched == [
        {"symbol": "AAPL", "close": 180.0},
        {"symbol": "MSFT", "close": 410.25},
    ]
    assert "Skipping invalid quote for watch symbol BAD1" in caplog.text
    assert "Skipping invalid quote for watch symbol BAD2" in caplog.text
    # Sentinel / blank watches never reach the fetcher.
    assert [c.args[0] for c in fetcher.fetch_symbol_data.call_args_list] == [
        "BAD1",
        "BAD2",
        "MSFT",
    ]

def test_stocks_from_daily_df_skips_invalid_closes(caplog):
    """One corrupt saved row must not wipe the rest of the daily dataset."""
    df = pd.DataFrame(
        [
            {"symbol": "AAPL", "close": 180.0},
            {"symbol": "BAD", "close": "n/a"},
            {"symbol": "", "close": 10.0},
            {"symbol": "MSFT", "close": "410.5"},
            {"symbol": "GOOG", "close": float("nan")},
            # Use a real ticker: "INF" is an invalid ticker sentinel.
            {"symbol": "TSLA", "close": float("inf")},
        ]
    )

    with caplog.at_level("WARNING"):
        stocks = _stocks_from_daily_df(df)

    assert stocks == [
        {"symbol": "AAPL", "close": 180.0},
        {"symbol": "MSFT", "close": 410.5},
    ]
    assert "Skipping invalid saved quote for BAD" in caplog.text
    assert "Skipping invalid saved quote for GOOG" in caplog.text
    assert "Skipping invalid saved quote for TSLA" in caplog.text


def test_stocks_from_daily_df_skips_invalid_symbol_tokens():
    """None/NaN/sentinel symbols must not become fake NONE/NAN tickers."""
    df = pd.DataFrame(
        [
            {"symbol": " aapl ", "close": 180.0},
            {"symbol": None, "close": 10.0},
            {"symbol": float("nan"), "close": 20.0},
            {"symbol": "nan", "close": 30.0},
            {"symbol": "NONE", "close": 40.0},
            {"symbol": "MSFT", "close": 410.0},
        ]
    )

    stocks = _stocks_from_daily_df(df)

    assert stocks == [
        {"symbol": "AAPL", "close": 180.0},
        {"symbol": "MSFT", "close": 410.0},
    ]


@patch("src.alerts.alert_runner.AlertEngine")
@patch("src.alerts.alert_runner.get_enabled_watch_symbols", return_value=[])
@patch("dashboard.backend.services.data_loader.get_data_loader")
def test_evaluate_alerts_keeps_valid_rows_when_saved_close_is_corrupt(
    mock_get_loader, _mock_watch_symbols, mock_engine_cls
):
    loader = MagicMock()
    loader.get_latest_date.return_value = "2026-05-20"
    loader.load_daily_data.return_value = pd.DataFrame(
        [
            {"symbol": "AAPL", "close": 180.0},
            {"symbol": "BAD", "close": "not-a-price"},
        ]
    )
    mock_get_loader.return_value = loader
    engine = MagicMock()
    engine.evaluate.return_value = []
    mock_engine_cls.from_config.return_value = engine

    result = evaluate_alerts_from_latest_data(fetch_missing_quotes=False)

    assert result["message"] == "No alerts triggered on latest data."
    engine.evaluate.assert_called_once_with([{"symbol": "AAPL", "close": 180.0}])


@patch("src.alerts.alert_runner.AlertEngine")
def test_evaluate_alerts_no_engine(mock_engine_cls):
    mock_engine_cls.from_config.return_value = None

    result = evaluate_alerts_from_latest_data()

    assert result["triggered"] == 0
    assert result["message"] == "No active watches configured."


@patch("src.alerts.alert_runner.AlertEngine")
@patch("src.alerts.alert_runner.get_enabled_watch_symbols", return_value=[])
@patch("dashboard.backend.services.data_loader.get_data_loader")
def test_evaluate_alerts_no_data(mock_get_loader, _mock_watch_symbols, mock_engine_cls):
    mock_engine_cls.from_config.return_value = MagicMock()
    mock_get_loader.return_value.load_daily_data.side_effect = ValueError("missing")

    result = evaluate_alerts_from_latest_data(fetch_missing_quotes=False)

    assert result["triggered"] == 0
    assert result["message"] == "No market data available."


def test_get_enabled_watch_symbols(tmp_path, monkeypatch):
    config_path = tmp_path / "alerts.json"
    config_path.write_text(
        """
        {
          "alerts": [
            {"id": "a", "enabled": true, "condition": {"type": "price_threshold", "symbol": "aapl"}},
            {"id": "b", "enabled": false, "condition": {"type": "price_threshold", "symbol": "MSFT"}},
            {"id": "c", "enabled": true, "condition": {"type": "screening_match", "filters": {}}}
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_HELM_ALERTS_CONFIG", str(config_path))
    assert get_enabled_watch_symbols() == ["AAPL"]


def test_get_enabled_watch_symbols_strips_and_rejects_sentinels(tmp_path, monkeypatch):
    """Padded watches must match quotes; blank/NaN symbols must not enter the index."""
    config_path = tmp_path / "alerts.json"
    config_path.write_text(
        """
        {
          "alerts": [
            {"id": "a", "enabled": true, "condition": {"type": "price_threshold", "symbol": " aapl "}},
            {"id": "b", "enabled": true, "condition": {"type": "price_threshold", "symbol": "  "}},
            {"id": "c", "enabled": true, "condition": {"type": "price_threshold", "symbol": "nan"}},
            {"id": "d", "enabled": true, "condition": {"type": "price_threshold", "symbol": "msft"}}
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_HELM_ALERTS_CONFIG", str(config_path))
    assert get_enabled_watch_symbols() == ["AAPL", "MSFT"]
"""Tests for alert evaluation against saved daily data."""

from unittest.mock import MagicMock, patch

import pandas as pd

from src.alerts.alert_paths import get_enabled_watch_symbols
from src.alerts.alert_runner import _fetch_missing_watch_quotes, evaluate_alerts_from_latest_data


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

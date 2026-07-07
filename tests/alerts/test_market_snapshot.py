"""Tests for shared market snapshot loading."""

from unittest.mock import MagicMock, patch

import pandas as pd

from src.alerts.market_snapshot import load_market_snapshot


def test_load_market_snapshot_reads_saved_prices():
    loader = MagicMock()
    loader.get_latest_date.return_value = "2026-06-09"
    loader.load_daily_data.return_value = pd.DataFrame(
        [
            {"symbol": "aapl", "close": "180.25"},
            {"symbol": "MSFT", "close": 420.0},
        ]
    )

    with (
        patch("src.alerts.market_snapshot._load_env"),
        patch("dashboard.backend.services.data_loader.get_data_loader", return_value=loader),
    ):
        last_date, prices, stocks = load_market_snapshot(fetch_missing_quotes=False)

    assert last_date == "2026-06-09"
    assert prices == {"AAPL": 180.25, "MSFT": 420.0}
    assert stocks == [
        {"symbol": "AAPL", "close": 180.25},
        {"symbol": "MSFT", "close": 420.0},
    ]


def test_load_market_snapshot_backfills_watch_quotes_when_saved_data_missing():
    loader = MagicMock()
    loader.get_latest_date.return_value = "2026-06-09"
    loader.load_daily_data.side_effect = ValueError("No daily data files found")

    with (
        patch("src.alerts.market_snapshot._load_env"),
        patch("dashboard.backend.services.data_loader.get_data_loader", return_value=loader),
        patch(
            "src.alerts.market_snapshot._fetch_missing_watch_quotes",
            return_value=[{"symbol": "NVDA", "price": "900.50"}],
        ) as fetch_missing,
    ):
        last_date, prices, stocks = load_market_snapshot(["nvda"])

    assert last_date == "2026-06-09"
    assert prices == {"NVDA": 900.5}
    assert stocks == [{"symbol": "NVDA", "price": "900.50"}]
    fetch_missing.assert_called_once_with([], ["NVDA"])

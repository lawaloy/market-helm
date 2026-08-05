"""Analyzer must soft-fail when ranking columns are absent from fetch rows."""

import math

from src.analysis.analyzer import StockAnalyzer


def test_analyze_daily_data_missing_ranking_columns_returns_zeroed_summary():
    """Partial rows without change_percent/volume previously KeyError'd the day."""
    analyzer = StockAnalyzer()
    rows = [
        {"symbol": "AAPL", "name": "Apple"},
        {"symbol": "MSFT", "name": "Microsoft", "close": 400.0},
    ]

    result = analyzer.analyze_daily_data(rows)

    assert result["summary"]["total_stocks"] == 2
    assert result["summary"]["gainers"] == 0
    assert result["summary"]["losers"] == 0
    assert result["summary"]["unchanged"] == 0
    assert result["summary"]["average_change_percent"] == 0.0
    assert result["top_gainers"] == []
    assert result["top_losers"] == []
    assert result["top_volume"] == []


def test_analyze_daily_data_partial_columns_ranks_available_rows():
    analyzer = StockAnalyzer()
    rows = [
        {
            "symbol": "UP",
            "name": "Up",
            "change_percent": 3.5,
            "close": 10.0,
            "volume": 1_000_000,
        },
        {
            # Missing volume — still ranks on change; volume board skips it.
            "symbol": "MID",
            "name": "Mid",
            "change_percent": 1.0,
            "close": 20.0,
        },
    ]

    result = analyzer.analyze_daily_data(rows)

    assert result["summary"]["gainers"] == 2
    assert result["top_gainers"][0]["symbol"] == "UP"
    assert math.isfinite(result["summary"]["average_change_percent"])
    assert result["top_volume"][0]["symbol"] == "UP"


def test_analyze_daily_data_missing_name_column_falls_back_to_symbol():
    """Schema drift without a name column previously KeyError'd the whole day."""
    analyzer = StockAnalyzer()
    rows = [
        {
            "symbol": "AAPL",
            "change_percent": 2.5,
            "close": 190.0,
            "volume": 1_000_000,
        },
        {
            "symbol": "MSFT",
            "change_percent": -1.5,
            "close": 400.0,
            "volume": 2_000_000,
        },
    ]

    result = analyzer.analyze_daily_data(rows)

    assert result["summary"]["total_stocks"] == 2
    assert result["top_gainers"][0]["symbol"] == "AAPL"
    assert result["top_gainers"][0]["name"] == "AAPL"
    assert result["top_losers"][0]["symbol"] == "MSFT"
    assert result["top_losers"][0]["name"] == "MSFT"
    assert result["top_volume"][0]["symbol"] == "MSFT"
    assert result["top_volume"][0]["name"] == "MSFT"


def test_analyze_daily_data_nan_name_falls_back_and_skips_blank_symbols():
    """NaN names must not enter leaderboards (summary save uses allow_nan=False)."""
    analyzer = StockAnalyzer()
    rows = [
        {
            "symbol": "KEEP",
            "name": "Keep Co",
            "change_percent": 1.0,
            "close": 10.0,
            "volume": 100,
        },
        {
            "symbol": "NANAME",
            "name": float("nan"),
            "change_percent": 4.0,
            "close": 11.0,
            "volume": 200,
        },
        {
            "symbol": "",
            "name": "Ghost",
            "change_percent": 9.0,
            "close": 12.0,
            "volume": 300,
        },
        {
            "symbol": float("nan"),
            "name": "Also Ghost",
            "change_percent": 8.0,
            "close": 13.0,
            "volume": 400,
        },
    ]

    result = analyzer.analyze_daily_data(rows)

    gainer_symbols = [row["symbol"] for row in result["top_gainers"]]
    assert gainer_symbols[0] == "NANAME"
    assert result["top_gainers"][0]["name"] == "NANAME"
    assert "" not in gainer_symbols
    assert "KEEP" in gainer_symbols
    for board in (result["top_gainers"], result["top_losers"], result["top_volume"]):
        for row in board:
            assert row["symbol"]
            assert isinstance(row["name"], str)
            assert not isinstance(row["name"], float)
            assert row["name"].lower() not in {"nan", "none"}
            assert math.isfinite(row["change_percent"])

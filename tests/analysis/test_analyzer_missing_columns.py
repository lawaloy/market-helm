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

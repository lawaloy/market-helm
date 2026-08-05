"""Daily exchange_statistics must skip sentinel / non-finite exchange_code labels."""

import json

from src.analysis.analyzer import StockAnalyzer


def test_analyze_daily_data_skips_sentinel_exchange_codes():
    """CSV/API can stringify NaN as 'nan'; keep real exchanges only."""
    analyzer = StockAnalyzer()
    rows = [
        {
            "symbol": "AAPL",
            "name": "Apple",
            "change_percent": 1.0,
            "close": 180.0,
            "volume": 1_000,
            "exchange_code": "NASDAQ",
        },
        {
            "symbol": "BAD",
            "name": "Bad Ex",
            "change_percent": 2.0,
            "close": 50.0,
            "volume": 2_000,
            "exchange_code": "nan",
        },
        {
            "symbol": "NONE",
            "name": "None Ex",
            "change_percent": -1.0,
            "close": 40.0,
            "volume": 3_000,
            "exchange_code": "None",
        },
        {
            "symbol": "NULLISH",
            "name": "Nullish",
            "change_percent": 0.5,
            "close": 30.0,
            "volume": 4_000,
            "exchange_code": float("nan"),
        },
    ]

    result = analyzer.analyze_daily_data(rows)
    exchange_stats = result["exchange_statistics"]

    assert list(exchange_stats.keys()) == ["NASDAQ"]
    assert exchange_stats["NASDAQ"]["stock_count"] == 1
    assert exchange_stats["NASDAQ"]["avg_change_percent"] == 1.0
    assert "nan" not in exchange_stats
    assert "None" not in exchange_stats
    json.dumps(result, allow_nan=False)

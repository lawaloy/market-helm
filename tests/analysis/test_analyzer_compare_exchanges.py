"""compare_exchanges must soft-fail missing columns and non-finite change/volume."""

import json
import math

from src.analysis.analyzer import StockAnalyzer


def test_compare_exchanges_missing_columns_returns_zeroed_stats():
    """Partial rows without change_percent/volume previously KeyError'd the batch."""
    analyzer = StockAnalyzer()
    result = analyzer.compare_exchanges(
        {
            "NYSE": [{"symbol": "AAPL"}, {"symbol": "MSFT", "close": 400.0}],
            "EMPTY": [],
        }
    )

    assert "EMPTY" not in result
    assert result["NYSE"]["stock_count"] == 2
    assert result["NYSE"]["average_change_percent"] == 0.0
    assert result["NYSE"]["total_volume"] == 0
    assert result["NYSE"]["gainers"] == 0
    assert result["NYSE"]["losers"] == 0
    json.dumps(result, allow_nan=False)


def test_compare_exchanges_skips_nonfinite_change_and_volume():
    """Inf volume previously OverflowError'd int(); Inf change inflated gainers."""
    analyzer = StockAnalyzer()
    result = analyzer.compare_exchanges(
        {
            "NASDAQ": [
                {
                    "symbol": "GOOD",
                    "change_percent": 1.5,
                    "volume": 1_000_000,
                },
                {
                    "symbol": "INFVOL",
                    "change_percent": 9.0,
                    "volume": float("inf"),
                },
                {
                    "symbol": "NANPCT",
                    "change_percent": float("nan"),
                    "volume": 500_000,
                },
                {
                    "symbol": "INFPCT",
                    "change_percent": float("inf"),
                    "volume": 100,
                },
            ]
        }
    )

    stats = result["NASDAQ"]
    assert stats["stock_count"] == 4
    # Change and volume are filtered independently (same as tracker index compare).
    assert stats["average_change_percent"] == 5.25  # mean(1.5, 9.0)
    assert stats["total_volume"] == 1_500_100  # 1e6 + 5e5 + 100; Inf volume dropped
    assert stats["gainers"] == 2
    assert stats["losers"] == 0
    assert math.isfinite(stats["average_change_percent"])
    json.dumps(result, allow_nan=False)


def test_compare_exchanges_all_dirty_rows_stay_json_safe():
    analyzer = StockAnalyzer()
    result = analyzer.compare_exchanges(
        {
            "X": [
                {"change_percent": float("nan"), "volume": float("nan")},
                {"change_percent": "n/a", "volume": None},
            ]
        }
    )

    stats = result["X"]
    assert stats["stock_count"] == 2
    assert stats["average_change_percent"] == 0.0
    assert stats["total_volume"] == 0
    assert stats["gainers"] == 0
    assert stats["losers"] == 0
    json.dumps(result, allow_nan=False)

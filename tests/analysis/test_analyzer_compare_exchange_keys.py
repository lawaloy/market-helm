"""compare_exchanges must skip sentinel / non-finite exchange keys like daily stats."""

import json

from src.analysis.analyzer import StockAnalyzer


def test_compare_exchanges_skips_sentinel_and_nonfinite_keys():
    analyzer = StockAnalyzer()
    result = analyzer.compare_exchanges(
        {
            "NYSE": [
                {"symbol": "IBM", "change_percent": 1.0, "volume": 1000},
            ],
            float("nan"): [
                {"symbol": "POISON", "change_percent": 9.0, "volume": 999},
            ],
            "nan": [
                {"symbol": "FAKE", "change_percent": 2.0, "volume": 500},
            ],
            None: [
                {"symbol": "NONE", "change_percent": 3.0, "volume": 250},
            ],
            "NASDAQ": [
                {"symbol": "AAPL", "change_percent": -0.5, "volume": 2000},
            ],
        }
    )

    assert set(result) == {"NYSE", "NASDAQ"}
    assert all(isinstance(k, str) for k in result)
    assert "nan" not in {k.lower() for k in result}
    assert result["NYSE"]["stock_count"] == 1
    assert result["NASDAQ"]["losers"] == 1
    json.dumps(result, allow_nan=False)

"""Projection batch must skip non-dict rows instead of aborting the daily run."""

from src.analysis.projector import StockProjector


def _good(symbol: str, change: float = 4.0) -> dict:
    return {
        "symbol": symbol,
        "name": symbol,
        "close": 100.0,
        "change_percent": change,
        "volume": 8_000_000,
        "market_cap": 50_000_000_000,
        "previous_close": 96.0,
    }


def test_generate_projections_skips_non_dict_rows():
    projector = StockProjector()
    rows = [
        _good("OK1"),
        None,
        "poison",
        ["not", "a", "dict"],
        _good("OK2", change=-3.0),
        42,
    ]

    projections = projector.generate_projections(rows)

    assert set(projections) == {"OK1", "OK2"}
    assert projections["OK1"]["symbol"] == "OK1"
    assert projections["OK2"]["symbol"] == "OK2"


def test_generate_projections_all_non_dict_returns_empty():
    projector = StockProjector()
    assert projector.generate_projections([None, "x", 1]) == {}

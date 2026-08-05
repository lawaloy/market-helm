"""generate_projections must soft-fail non-list roots instead of TypeError."""

from src.analysis.projector import StockProjector


def test_generate_projections_none_root_returns_empty():
    projector = StockProjector()
    assert projector.generate_projections(None) == {}


def test_generate_projections_dict_root_returns_empty():
    """A single stock dict must not be iterated as key characters."""
    projector = StockProjector()
    assert projector.generate_projections({"symbol": "AAPL", "close": 100.0}) == {}


def test_generate_projections_scalar_root_returns_empty():
    projector = StockProjector()
    assert projector.generate_projections("not-a-list") == {}
    assert projector.generate_projections(42) == {}

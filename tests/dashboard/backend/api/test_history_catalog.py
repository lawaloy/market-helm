"""Tests for history symbol catalog builders."""

from unittest.mock import MagicMock, patch

import pandas as pd

from dashboard.backend.api.history import build_symbol_catalog


@patch("dashboard.backend.api.history.load_index_symbol_names", return_value={"AAPL": "Apple Inc."})
@patch("dashboard.backend.api.history.get_data_loader")
def test_build_symbol_catalog_skips_none_nan_blank_projection_symbols(
    mock_get_loader, _mock_index_names
):
    """Corrupt projection symbols must not leak as NONE/NAN/blank pickers."""
    loader = MagicMock()
    loader.load_projections.return_value = pd.DataFrame(
        {
            "symbol": ["AAPL", None, float("nan"), "", "  ", "msft", "GOOG"],
            "name": [
                "Apple Inc.",
                "Nope",
                "Nope",
                "Nope",
                "Nope",
                "Microsoft",
                "Alphabet",
            ],
        }
    )
    mock_get_loader.return_value = loader

    symbols, names = build_symbol_catalog()

    assert "NONE" not in symbols
    assert "NAN" not in symbols
    assert "" not in symbols
    assert "AAPL" in symbols
    assert "MSFT" in symbols
    assert "GOOG" in symbols
    assert names["MSFT"] == "Microsoft"
    assert names["GOOG"] == "Alphabet"

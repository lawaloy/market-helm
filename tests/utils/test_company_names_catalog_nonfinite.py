"""Catalog names must be cleaned — pytickersymbols can leak NaN/Inf floats."""

from unittest.mock import MagicMock, patch

import pytest

import src.utils.company_names as company_names


def setup_function():
    company_names._name_cache.clear()


@pytest.mark.parametrize("poison", [float("nan"), float("inf"), float("-inf"), "nan", "INF", None, ""])
def test_resolve_skips_nonfinite_catalog_name_and_falls_back_to_symbol(poison):
    mock_data = MagicMock()
    mock_data.get_stocks_by_index.side_effect = lambda index: (
        [{"symbol": "AAPL", "name": poison}] if index == "S&P 500" else []
    )
    with patch("pytickersymbols.PyTickerSymbols", return_value=mock_data):
        assert company_names.resolve_company_name("AAPL") == "AAPL"

    assert company_names._name_cache["AAPL"] == "AAPL"


def test_resolve_caches_cleaned_catalog_name_not_raw_float():
    mock_data = MagicMock()
    mock_data.get_stocks_by_index.side_effect = lambda index: (
        [{"symbol": "MSFT", "name": "  Microsoft Corporation  "}]
        if index == "S&P 500"
        else []
    )
    with patch("pytickersymbols.PyTickerSymbols", return_value=mock_data):
        assert company_names.resolve_company_name("MSFT") == "Microsoft Corporation"

    assert company_names._name_cache["MSFT"] == "Microsoft Corporation"


def test_resolve_skips_poison_index_entry_and_uses_later_index():
    """First index may return a NaN name; a later index with a real name must win."""

    def stocks(index: str):
        if index == "S&P 500":
            return [{"symbol": "GOOG", "name": float("nan")}]
        if index == "NASDAQ 100":
            return [{"symbol": "GOOG", "name": "Alphabet Inc."}]
        return []

    mock_data = MagicMock()
    mock_data.get_stocks_by_index.side_effect = stocks
    with patch("pytickersymbols.PyTickerSymbols", return_value=mock_data):
        assert company_names.resolve_company_name("GOOG") == "Alphabet Inc."

    assert company_names._name_cache["GOOG"] == "Alphabet Inc."

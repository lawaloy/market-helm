"""Tests for company name resolution and enrichment."""

from unittest.mock import MagicMock, patch

import src.utils.company_names as company_names


def setup_function():
    company_names._name_cache.clear()


def test_resolve_prefers_non_symbol_fallback():
    assert company_names.resolve_company_name("AAPL", "Apple Inc.") == "Apple Inc."
    assert company_names._name_cache == {}


def test_resolve_uses_cache_before_lookup():
    company_names._name_cache["MSFT"] = "Microsoft Corporation"
    with patch("pytickersymbols.PyTickerSymbols") as mock_cls:
        assert company_names.resolve_company_name("MSFT") == "Microsoft Corporation"
        mock_cls.assert_not_called()


def test_resolve_looks_up_index_and_caches_name():
    mock_data = MagicMock()
    mock_data.get_stocks_by_index.side_effect = lambda index: (
        [{"symbol": "AAPL", "name": "Apple Inc."}] if index == "S&P 500" else []
    )
    with patch("pytickersymbols.PyTickerSymbols", return_value=mock_data):
        assert company_names.resolve_company_name("AAPL") == "Apple Inc."

    assert company_names._name_cache["AAPL"] == "Apple Inc."
    mock_data.get_stocks_by_index.assert_any_call("S&P 500")


def test_resolve_caches_symbol_when_lookup_fails():
    with patch("pytickersymbols.PyTickerSymbols", side_effect=ImportError("missing")):
        assert company_names.resolve_company_name("ZZZZ") == "ZZZZ"
    assert company_names._name_cache["ZZZZ"] == "ZZZZ"


def test_enrich_skips_empty_symbol_and_keeps_existing_names():
    rows = [
        {"symbol": "", "name": ""},
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "MSFT", "name": "MSFT"},
        {"symbol": "GOOG"},
    ]
    with patch.object(
        company_names,
        "resolve_company_name",
        side_effect=lambda symbol, fallback="": f"Resolved-{symbol}",
    ) as mock_resolve:
        out = company_names.enrich_stock_data_with_names(rows)

    assert out is rows
    assert rows[0]["name"] == ""
    assert rows[1]["name"] == "Apple Inc."
    assert rows[2]["name"] == "Resolved-MSFT"
    assert rows[3]["name"] == "Resolved-GOOG"
    assert mock_resolve.call_count == 2

"""enrich_stock_data_with_names must skip non-dict rows without aborting peers."""

from unittest.mock import patch

import src.utils.company_names as company_names


def setup_function():
    company_names._name_cache.clear()


def test_enrich_skips_non_dict_rows_and_continues():
    rows = [
        {"symbol": "AAPL", "name": "AAPL"},
        None,
        "poison",
        ["not", "a", "row"],
        42,
        {"symbol": "MSFT", "name": "MSFT"},
    ]
    with patch.object(
        company_names,
        "resolve_company_name",
        side_effect=lambda symbol, fallback="": f"Resolved-{symbol}",
    ) as mock_resolve:
        out = company_names.enrich_stock_data_with_names(rows)

    assert out is rows
    assert rows[0]["name"] == "Resolved-AAPL"
    assert rows[1] is None
    assert rows[2] == "poison"
    assert rows[3] == ["not", "a", "row"]
    assert rows[4] == 42
    assert rows[5]["name"] == "Resolved-MSFT"
    assert mock_resolve.call_count == 2


def test_enrich_empty_and_all_non_dict_is_noop():
    assert company_names.enrich_stock_data_with_names([]) == []
    poison = [None, "x", 1]
    assert company_names.enrich_stock_data_with_names(poison) is poison
    assert poison == [None, "x", 1]

"""
Shared company name resolution (pytickersymbols).
Used when saving data so names are stored at write time.
"""
from typing import Dict

from src.utils.tickers import normalize_ticker

# Cached symbol->name lookup - built once, reused
_name_cache: Dict[str, str] = {}


def resolve_company_name(symbol: str, fallback: str = "") -> str:
    """
    Resolve company name when API returns symbol. Uses pytickersymbols.
    Returns real name for S&P 500, NASDAQ 100, Dow Jones symbols.
    """
    key = normalize_ticker(symbol)
    if key is None:
        return str(fallback).strip() if fallback else ""

    # Prefer a real display name over the ticker itself (any case/padding).
    if fallback:
        fb = str(fallback).strip()
        if fb and normalize_ticker(fb) != key:
            return fb

    if key in _name_cache:
        return _name_cache[key]
    try:
        from pytickersymbols import PyTickerSymbols
        data = PyTickerSymbols()
        for index_name in ["S&P 500", "NASDAQ 100", "Dow Jones"]:
            try:
                for s in data.get_stocks_by_index(index_name):
                    if normalize_ticker(s.get("symbol")) == key and s.get("name"):
                        _name_cache[key] = s["name"]
                        return s["name"]
            except Exception:
                continue
    except Exception:
        pass
    _name_cache[key] = key
    return key


def enrich_stock_data_with_names(data: list) -> list:
    """
    Enrich each stock dict with resolved company name when name is missing or equals symbol.
    Modifies in place and returns the same list.
    """
    for row in data:
        # Skip poison / hand-edited non-dict rows so save_daily_data can continue.
        if not isinstance(row, dict):
            continue
        key = normalize_ticker(row.get("symbol"))
        if key is None:
            continue
        # Canonicalize stored symbol so downstream joins stay clean.
        row["symbol"] = key
        raw_name = row.get("name", key)
        name_as_ticker = normalize_ticker(raw_name) == key if raw_name else True
        if not raw_name or name_as_ticker:
            row["name"] = resolve_company_name(key, raw_name or key)
    return data

"""Resolve latest prices for alert symbol pickers."""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

logger = logging.getLogger(__name__)

_MAX_LIVE_FETCH = 15
_MAX_WORKERS = 4


def _load_env() -> None:
    try:
        from src.cli.alerts_commands import _load_env as cli_load_env

        cli_load_env()
    except Exception:
        pass


def prices_from_saved_daily_data() -> Dict[str, float]:
    """Prices from the newest daily_data CSV on disk."""
    from dashboard.backend.services.data_loader import get_data_loader

    prices: Dict[str, float] = {}
    try:
        loader = get_data_loader()
        df = loader.load_daily_data()
    except ValueError:
        return prices

    for _, row in df.iterrows():
        symbol = str(row.get("symbol", "")).upper()
        close = row.get("close", row.get("price"))
        if not symbol or close is None:
            continue
        try:
            value = float(close)
        except (TypeError, ValueError):
            continue
        # float("nan") succeeds; skip so alert quotes stay JSON-safe.
        if not math.isfinite(value):
            continue
        prices[symbol] = value
    return prices


def resolve_symbol_prices(
    symbols: List[str],
    *,
    fetch_missing: bool = True,
) -> Dict[str, float]:
    """
    Return prices for the requested symbols.
    Uses saved daily data first, then optional live Finnhub quotes for gaps.
    """
    normalized = list(dict.fromkeys(str(symbol).upper() for symbol in symbols if str(symbol).strip()))
    if not normalized:
        return {}

    saved = prices_from_saved_daily_data()
    prices: Dict[str, float] = {symbol: saved[symbol] for symbol in normalized if symbol in saved}
    if not fetch_missing:
        return prices

    missing = [symbol for symbol in normalized if symbol not in prices][:_MAX_LIVE_FETCH]
    if not missing:
        return prices

    _load_env()
    try:
        from src.services.data_fetcher import StockDataFetcher

        fetcher = StockDataFetcher(include_profile=False)
    except Exception as exc:
        logger.warning("Live quote fetch unavailable: %s", exc)
        return prices

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_one_quote, fetcher, symbol): symbol for symbol in missing}
        for future in as_completed(futures):
            symbol, close = future.result()
            if close is not None:
                prices[symbol] = close

    return prices


def _fetch_one_quote(fetcher, symbol: str) -> tuple[str, float | None]:
    try:
        row = fetcher.fetch_symbol_data(symbol)
    except Exception as exc:
        logger.debug("Quote fetch failed for %s: %s", symbol, exc)
        return symbol, None
    if not row:
        return symbol, None
    close = row.get("close", row.get("price"))
    if close is None:
        return symbol, None
    try:
        value = float(close)
    except (TypeError, ValueError):
        return symbol, None
    if not math.isfinite(value):
        return symbol, None
    return symbol, value

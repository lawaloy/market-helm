"""Evaluate configured alerts against the latest saved daily market data."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

from src.alerts.alert_engine import AlertEngine
from src.alerts.alert_paths import get_enabled_watch_symbols

logger = logging.getLogger(__name__)


def _load_env() -> None:
    try:
        from src.cli.alerts_commands import _load_env as cli_load_env

        cli_load_env()
    except Exception:
        pass


def _stocks_from_daily_df(df) -> List[Dict[str, Any]]:
    stocks: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        symbol = str(row.get("symbol", "")).upper()
        close = row.get("close", row.get("price"))
        if not symbol or close is None:
            continue
        try:
            close_value = float(close)
        except (TypeError, ValueError):
            logger.warning("Skipping invalid saved quote for %s: %r", symbol, close)
            continue
        # float("inf") is not NaN; reject all non-finite closes.
        if not math.isfinite(close_value):
            logger.warning("Skipping invalid saved quote for %s: %r", symbol, close)
            continue
        stocks.append({"symbol": symbol, "close": close_value})
    return stocks


def _fetch_missing_watch_quotes(
    stocks: List[Dict[str, Any]], watch_symbols: List[str]
) -> List[Dict[str, Any]]:
    """Fetch live quotes for watch symbols missing from saved daily data."""
    if not watch_symbols:
        return stocks

    present = {str(stock.get("symbol", "")).upper() for stock in stocks if stock.get("symbol")}
    missing = [symbol for symbol in watch_symbols if symbol not in present]
    if not missing:
        return stocks

    try:
        from src.services.data_fetcher import StockDataFetcher

        fetcher = StockDataFetcher(include_profile=False)
    except Exception as exc:
        logger.warning("Could not fetch watch symbols (API unavailable): %s", exc)
        return stocks

    enriched = list(stocks)
    for symbol in missing:
        try:
            row = fetcher.fetch_symbol_data(symbol)
        except Exception as exc:
            logger.warning("Failed to fetch quote for watch symbol %s: %s", symbol, exc)
            continue
        if not row:
            continue
        close = row.get("close", row.get("price"))
        if close is None:
            continue
        try:
            close_value = float(close)
        except (TypeError, ValueError):
            logger.warning("Skipping invalid quote for watch symbol %s: %r", symbol, close)
            continue
        if not math.isfinite(close_value):
            logger.warning("Skipping invalid quote for watch symbol %s: %r", symbol, close)
            continue
        enriched.append({"symbol": symbol.upper(), "close": close_value})
        logger.info("Fetched live quote for watch symbol %s", symbol)

    return enriched


def evaluate_alerts_from_latest_data(*, fetch_missing_quotes: bool = True) -> Dict[str, Any]:
    """
    Run all enabled watches against the newest daily_data CSV on disk.
    When fetch_missing_quotes is True, also pulls live Finnhub quotes for
    watch symbols that are not in the saved CSV (common with REFRESH_TOP_N=10).
    """
    _load_env()
    engine = AlertEngine.from_config()
    if not engine:
        return {
            "triggered": 0,
            "events": [],
            "last_data_date": None,
            "message": "No active watches configured.",
        }

    from dashboard.backend.services.data_loader import get_data_loader

    last_date: str | None = None
    stocks: List[Dict[str, Any]] = []
    try:
        loader = get_data_loader()
        last_date = loader.get_latest_date()
        stocks = _stocks_from_daily_df(loader.load_daily_data())
    except ValueError:
        stocks = []

    watch_symbols = get_enabled_watch_symbols()
    if fetch_missing_quotes and watch_symbols:
        stocks = _fetch_missing_watch_quotes(stocks, watch_symbols)

    if not stocks:
        return {
            "triggered": 0,
            "events": [],
            "last_data_date": last_date,
            "message": "No market data available.",
        }

    events = engine.evaluate(stocks)
    return {
        "triggered": len(events),
        "events": events,
        "last_data_date": last_date,
        "message": None if events else "No alerts triggered on latest data.",
    }

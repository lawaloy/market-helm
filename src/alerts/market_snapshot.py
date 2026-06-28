"""Load shared market prices once per evaluation tick."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.alerts.alert_runner import _fetch_missing_watch_quotes, _load_env, _stocks_from_daily_df


def load_market_snapshot(
    watch_symbols: Optional[List[str]] = None,
    *,
    fetch_missing_quotes: bool = True,
) -> Tuple[Optional[str], Dict[str, float], List[Dict[str, Any]]]:
    """
    Return (last_data_date, symbol->close prices, stock rows).
    Prices include saved daily data plus optional live quotes for missing symbols.
    """
    _load_env()
    last_date: Optional[str] = None
    stocks: List[Dict[str, Any]] = []

    try:
        from dashboard.backend.services.data_loader import get_data_loader

        loader = get_data_loader()
        last_date = loader.get_latest_date()
        stocks = _stocks_from_daily_df(loader.load_daily_data())
    except ValueError:
        stocks = []

    symbols = [str(s).upper() for s in (watch_symbols or []) if str(s).strip()]
    if fetch_missing_quotes and symbols:
        stocks = _fetch_missing_watch_quotes(stocks, symbols)

    prices: Dict[str, float] = {}
    for stock in stocks:
        symbol = str(stock.get("symbol") or "").upper()
        close = stock.get("close", stock.get("price"))
        if not symbol or close is None:
            continue
        try:
            prices[symbol] = float(close)
        except (TypeError, ValueError):
            continue

    return last_date, prices, stocks

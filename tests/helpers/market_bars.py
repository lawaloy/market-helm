"""Shared helper to seed durable daily bars in tests (CSV daily_data removed)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Sequence, Union

from src.storage.market_bars import upsert_market_bars


def seed_daily_bars(
    data_dir: Union[str, Path],
    trade_date: Union[str, date],
    rows: Sequence[Dict[str, Any]],
) -> int:
    """Upsert quote rows for one trade date into market_bars under ``data_dir``."""
    return upsert_market_bars(list(rows), trade_date, data_dir=data_dir, source="test")


def seed_simple_bars(
    data_dir: Union[str, Path],
    trade_date: Union[str, date],
    *,
    symbol: str = "AAPL",
    close: float = 100.0,
    **extra: Any,
) -> int:
    row: Dict[str, Any] = {"symbol": symbol, "close": close, **extra}
    return seed_daily_bars(data_dir, trade_date, [row])

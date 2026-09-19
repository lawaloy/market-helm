"""Load per-symbol close history for technical alert rules.

Preferred source is the live market-data provider (Finnhub daily candles).
Local ``daily_data_*.csv`` files remain a fallback for offline / no-key runs
and for the broader product surface that still stores market snapshots as files.
"""

from __future__ import annotations

import csv
import logging
import math
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from src.utils.tickers import normalize_ticker

logger = logging.getLogger(__name__)

_DAILY_FILE = re.compile(r"^daily_data_(\d{4}-\d{2}-\d{2})\.csv$")

# RSI(14) needs 15 closes; Wilder smoothing benefits from extra warm-up bars.
# ~90 calendar days covers holidays/weekends while staying within free-tier cost.
DEFAULT_PROVIDER_LOOKBACK_DAYS = 90
DEFAULT_PROVIDER_MIN_BARS = 15


def resolve_market_data_dir(data_dir: Optional[str | Path] = None) -> Path:
    """Same resolution order as DataStorage: explicit → DATA_DIR → ./data."""
    if data_dir is not None:
        return Path(data_dir)
    return Path(os.getenv("DATA_DIR") or "data")


def _finite_close(raw) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _close_from_row(row: dict) -> Optional[float]:
    for key in ("close", "price", "c"):
        if key in row:
            value = _finite_close(row.get(key))
            if value is not None:
                return value
    return None


def closes_from_candle_payload(payload: object) -> List[float]:
    """Extract chronological closes from a Finnhub-style candle response."""
    if not isinstance(payload, dict):
        return []
    status = str(payload.get("s") or "ok").lower()
    if status != "ok":
        return []
    raw_closes = payload.get("c")
    raw_times = payload.get("t")
    if not isinstance(raw_closes, list) or not raw_closes:
        return []

    if isinstance(raw_times, list) and len(raw_times) == len(raw_closes):
        paired: List[tuple[float, float]] = []
        for ts, close in zip(raw_times, raw_closes):
            value = _finite_close(close)
            if value is None:
                continue
            try:
                stamp = float(ts)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(stamp):
                continue
            paired.append((stamp, value))
        paired.sort(key=lambda item: item[0])
        return [value for _ts, value in paired]

    closes: List[float] = []
    for close in raw_closes:
        value = _finite_close(close)
        if value is not None:
            closes.append(value)
    return closes


def load_symbol_closes_from_provider(
    symbol: str,
    *,
    days: int = DEFAULT_PROVIDER_LOOKBACK_DAYS,
    client=None,
) -> List[float]:
    """Fetch daily closes from Finnhub candles. Empty list on any soft failure."""
    ticker = normalize_ticker(symbol)
    if not ticker:
        return []
    try:
        lookback = int(days)
    except (TypeError, ValueError):
        lookback = DEFAULT_PROVIDER_LOOKBACK_DAYS
    if lookback < DEFAULT_PROVIDER_MIN_BARS:
        lookback = DEFAULT_PROVIDER_LOOKBACK_DAYS

    try:
        if client is None:
            from src.services.api_client import StockAPIClient

            client = StockAPIClient()
        payload = client.get_candle_data(ticker, resolution="D", days=lookback)
    except Exception as exc:
        logger.info("Provider candle history unavailable for %s: %s", ticker, exc)
        return []

    closes = closes_from_candle_payload(payload)
    if len(closes) < DEFAULT_PROVIDER_MIN_BARS:
        logger.info(
            "Provider candle history for %s has only %d usable closes",
            ticker,
            len(closes),
        )
    return closes


def load_symbol_closes_from_csv(
    symbol: str,
    *,
    data_dir: Optional[str | Path] = None,
    max_files: int = 120,
) -> List[float]:
    """
    Chronological closes for ``symbol`` from ``daily_data_YYYY-MM-DD.csv`` files.

    Missing dates or missing rows are skipped. Returns an empty list when the
    ticker is blank or no usable files exist.
    """
    ticker = normalize_ticker(symbol)
    if not ticker:
        return []

    root = resolve_market_data_dir(data_dir)
    if not root.is_dir():
        return []

    dated: List[tuple[str, Path]] = []
    try:
        for path in root.iterdir():
            if not path.is_file():
                continue
            match = _DAILY_FILE.match(path.name)
            if match:
                dated.append((match.group(1), path))
    except OSError as exc:
        logger.warning("Could not list market data in %s: %s", root, exc)
        return []

    dated.sort(key=lambda item: item[0])
    if max_files > 0 and len(dated) > max_files:
        dated = dated[-max_files:]

    closes: List[float] = []
    for _day, path in dated:
        try:
            with open(path, newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    if not isinstance(row, dict):
                        continue
                    if normalize_ticker(row.get("symbol")) != ticker:
                        continue
                    close = _close_from_row(row)
                    if close is not None:
                        closes.append(close)
                    break
        except OSError as exc:
            logger.warning("Could not read %s: %s", path, exc)
            continue
        except csv.Error as exc:
            logger.warning("Malformed CSV %s: %s", path, exc)
            continue
    return closes


def load_symbol_closes(
    symbol: str,
    *,
    data_dir: Optional[str | Path] = None,
    max_files: int = 120,
    prefer_provider: bool = True,
    client=None,
) -> List[float]:
    """
    Chronological closes for technical rules.

    Tries the live provider first (when ``prefer_provider``), then falls back to
    local daily CSV snapshots so offline demos and key-less CI still work.
    """
    if prefer_provider:
        provider_closes = load_symbol_closes_from_provider(symbol, client=client)
        if len(provider_closes) >= DEFAULT_PROVIDER_MIN_BARS:
            return provider_closes
        if provider_closes:
            # Partial provider series — still prefer it when longer than CSV.
            csv_closes = load_symbol_closes_from_csv(
                symbol, data_dir=data_dir, max_files=max_files
            )
            return provider_closes if len(provider_closes) >= len(csv_closes) else csv_closes

    return load_symbol_closes_from_csv(
        symbol, data_dir=data_dir, max_files=max_files
    )


def merge_latest_close(
    closes: Sequence[float],
    latest: Optional[float],
) -> List[float]:
    """
    Append or replace the final close with a live/snapshot quote.

    Keeps RSI evaluation aligned with the price used for price_threshold rules
    on the same tick without inventing a new session file.
    """
    series = [float(value) for value in closes]
    if latest is None:
        return series
    try:
        value = float(latest)
    except (TypeError, ValueError):
        return series
    if not math.isfinite(value):
        return series
    if series and series[-1] == value:
        return series
    if series:
        # Same trading session: replace last bar with the fresher quote.
        return [*series[:-1], value]
    return [value]


def closes_by_symbol(
    symbols: Iterable[str],
    stocks: Sequence[dict],
    *,
    data_dir: Optional[str | Path] = None,
    prefer_provider: bool = True,
    client=None,
) -> Dict[str, List[float]]:
    """Load history for each symbol and overlay the snapshot close when present."""
    latest_by_symbol: Dict[str, float] = {}
    for stock in stocks:
        if not isinstance(stock, dict):
            continue
        ticker = normalize_ticker(stock.get("symbol"))
        if not ticker:
            continue
        close = _finite_close(stock.get("close", stock.get("price")))
        if close is not None:
            latest_by_symbol[ticker] = close

    result: Dict[str, List[float]] = {}
    for raw_symbol in symbols:
        ticker = normalize_ticker(raw_symbol)
        if not ticker or ticker in result:
            continue
        history = load_symbol_closes(
            ticker,
            data_dir=data_dir,
            prefer_provider=prefer_provider,
            client=client,
        )
        result[ticker] = merge_latest_close(history, latest_by_symbol.get(ticker))
    return result

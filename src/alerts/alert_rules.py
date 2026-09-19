"""
Alert rule evaluators.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence

from src.utils.tickers import normalize_ticker

from .indicators import compute_rsi

DEFAULT_RSI_PERIOD = 14
MIN_RSI_PERIOD = 2
MAX_RSI_PERIOD = 50
MAX_COMPOUND_LEAVES = 5
COMPOUND_OPS = frozenset({"and", "or"})
LEAF_CONDITION_TYPES = frozenset(
    {"price_threshold", "screening_match", "rsi_threshold"}
)


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == "less_than":
        return value < threshold
    if operator == "less_or_equal":
        return value <= threshold
    if operator == "greater_than":
        return value > threshold
    if operator == "greater_or_equal":
        return value >= threshold
    if operator == "equal":
        return value == threshold
    raise ValueError(f"Unsupported operator: {operator}")


def _finite_float(value) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite numeric value: {value!r}")
    return number


def evaluate_price_threshold(condition: Dict, stock: Dict) -> bool:
    """
    Evaluate a price threshold condition against a single stock record.
    """
    if not isinstance(condition, dict) or not isinstance(stock, dict):
        return False
    operator = condition.get("operator", "less_than")
    try:
        threshold = _finite_float(condition.get("value", 0))
        price = _finite_float(stock.get("close", 0))
        # Soft-fail unsupported operators too: AlertEngine.evaluate has no
        # per-alert try/except, so a raised ValueError would abort siblings.
        return _compare(price, operator, threshold)
    except (TypeError, ValueError):
        # Inf closes would otherwise compare True for greater_than and fire alerts.
        return False


def evaluate_screening_match(condition: Dict, stock: Dict) -> bool:
    """
    Evaluate a screening condition using simple numeric thresholds.
    Supported keys: volume_threshold, min_daily_change_pct, price_min, price_max.
    """
    if not isinstance(condition, dict) or not isinstance(stock, dict):
        return False
    raw_filters = condition.get("filters", {})
    # Hand-edited configs may set filters to null/list/string; treat as no filters.
    filters = raw_filters if isinstance(raw_filters, dict) else {}
    volume_threshold = filters.get("volume_threshold")
    min_daily_change_pct = filters.get("min_daily_change_pct")
    price_min = filters.get("price_min")
    price_max = filters.get("price_max")

    try:
        if volume_threshold is not None:
            volume = _finite_float(stock.get("volume", 0))
            if volume < _finite_float(volume_threshold):
                return False
        if min_daily_change_pct is not None:
            change_percent = _finite_float(stock.get("change_percent", 0))
            if abs(change_percent) < _finite_float(min_daily_change_pct):
                return False
        if price_min is not None:
            close = _finite_float(stock.get("close", 0))
            if close < _finite_float(price_min):
                return False
        if price_max is not None:
            close = _finite_float(stock.get("close", 0))
            if close > _finite_float(price_max):
                return False
    except (TypeError, ValueError):
        return False

    return True


def _rsi_period(condition: Dict) -> Optional[int]:
    raw = condition.get("period", DEFAULT_RSI_PERIOD)
    try:
        period = int(raw)
    except (TypeError, ValueError):
        return None
    if period < MIN_RSI_PERIOD or period > MAX_RSI_PERIOD:
        return None
    return period


def evaluate_rsi_threshold(
    condition: Dict,
    closes: Sequence[float],
) -> bool:
    """
    Evaluate an RSI threshold against a chronological close series.

    Condition shape::

        {
          "type": "rsi_threshold",
          "symbol": "AAPL",
          "period": 14,
          "operator": "less_than",
          "value": 30
        }
    """
    if not isinstance(condition, dict):
        return False
    period = _rsi_period(condition)
    if period is None:
        return False
    operator = condition.get("operator", "less_than")
    try:
        threshold = _finite_float(condition.get("value"))
    except (TypeError, ValueError):
        return False
    rsi = compute_rsi(closes, period)
    if rsi is None:
        return False
    try:
        return _compare(rsi, operator, threshold)
    except (TypeError, ValueError):
        return False


def _stock_for_symbol(stocks: Sequence, symbol: str) -> Optional[Dict]:
    ticker = normalize_ticker(symbol)
    if not ticker:
        return None
    for stock in stocks:
        if not isinstance(stock, dict):
            continue
        if normalize_ticker(stock.get("symbol")) == ticker:
            return stock
    return None


def evaluate_leaf_symbols(
    condition: Dict,
    stocks: Sequence,
    closes_by_symbol: Optional[Dict[str, Sequence[float]]] = None,
) -> List[str]:
    """Return symbols matched by a non-compound leaf condition."""
    if not isinstance(condition, dict):
        return []
    condition_type = condition.get("type")
    closes_by_symbol = closes_by_symbol or {}

    if condition_type == "price_threshold":
        symbol = normalize_ticker(condition.get("symbol"))
        if not symbol:
            return []
        stock = _stock_for_symbol(stocks, symbol)
        if stock and evaluate_price_threshold(condition, stock):
            return [symbol]
        return []

    if condition_type == "rsi_threshold":
        symbol = normalize_ticker(condition.get("symbol"))
        if not symbol:
            return []
        closes = closes_by_symbol.get(symbol) or []
        if evaluate_rsi_threshold(condition, closes):
            return [symbol]
        return []

    if condition_type == "screening_match":
        matched: List[str] = []
        for stock in stocks:
            if not isinstance(stock, dict):
                continue
            if evaluate_screening_match(condition, stock):
                symbol = normalize_ticker(stock.get("symbol"))
                if symbol:
                    matched.append(symbol)
        return matched

    return []


def evaluate_compound(
    condition: Dict,
    stocks: Sequence,
    closes_by_symbol: Optional[Dict[str, Sequence[float]]] = None,
) -> List[str]:
    """
    Evaluate a shallow AND/OR compound of leaf conditions.

    Nested compounds are rejected (soft-fail) so configs stay reviewable.
    """
    if not isinstance(condition, dict):
        return []
    op = str(condition.get("op") or "and").strip().lower()
    if op not in COMPOUND_OPS:
        return []
    leaves = condition.get("conditions")
    if not isinstance(leaves, list) or not leaves:
        return []
    if len(leaves) > MAX_COMPOUND_LEAVES:
        return []

    leaf_results: List[List[str]] = []
    for leaf in leaves:
        if not isinstance(leaf, dict):
            return []
        if leaf.get("type") == "compound":
            # Nesting is deferred — fail closed rather than recurse.
            return []
        if leaf.get("type") not in LEAF_CONDITION_TYPES:
            return []
        leaf_results.append(
            evaluate_leaf_symbols(leaf, stocks, closes_by_symbol=closes_by_symbol)
        )

    if op == "and":
        if not all(leaf_results):
            return []
        matched: List[str] = []
        seen = set()
        for symbols in leaf_results:
            for symbol in symbols:
                if symbol not in seen:
                    seen.add(symbol)
                    matched.append(symbol)
        return matched

    # OR
    matched = []
    seen = set()
    for symbols in leaf_results:
        for symbol in symbols:
            if symbol not in seen:
                seen.add(symbol)
                matched.append(symbol)
    return matched


def condition_watch_symbols(condition: Dict) -> List[str]:
    """Symbols referenced by a condition (for quote fetch / watch indexing)."""
    if not isinstance(condition, dict):
        return []
    condition_type = condition.get("type")
    if condition_type in {"price_threshold", "rsi_threshold"}:
        symbol = normalize_ticker(condition.get("symbol"))
        return [symbol] if symbol else []
    if condition_type == "compound":
        leaves = condition.get("conditions")
        if not isinstance(leaves, list):
            return []
        symbols: List[str] = []
        seen = set()
        for leaf in leaves:
            if not isinstance(leaf, dict) or leaf.get("type") == "compound":
                continue
            for symbol in condition_watch_symbols(leaf):
                if symbol not in seen:
                    seen.add(symbol)
                    symbols.append(symbol)
        return symbols
    return []


def primary_watch_symbol(condition: Dict) -> Optional[str]:
    """
    Single symbol for hosted evaluate_symbol indexing, or None when the
    condition spans multiple symbols / market-wide screening.
    """
    symbols = condition_watch_symbols(condition)
    if len(symbols) == 1:
        return symbols[0]
    return None


def collect_rsi_symbols(alerts: Iterable[Dict]) -> List[str]:
    """Unique symbols that need close history for RSI / compound RSI leaves."""
    needed: List[str] = []
    seen = set()

    def _walk(condition: Dict) -> None:
        if not isinstance(condition, dict):
            return
        ctype = condition.get("type")
        if ctype == "rsi_threshold":
            symbol = normalize_ticker(condition.get("symbol"))
            if symbol and symbol not in seen:
                seen.add(symbol)
                needed.append(symbol)
        elif ctype == "compound":
            leaves = condition.get("conditions")
            if isinstance(leaves, list):
                for leaf in leaves:
                    if isinstance(leaf, dict):
                        _walk(leaf)

    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        condition = alert.get("condition")
        if isinstance(condition, dict):
            _walk(condition)
    return needed

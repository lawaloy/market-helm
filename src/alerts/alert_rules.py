"""
Alert rule evaluators.
"""

import math
from typing import Dict


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
    operator = condition.get("operator", "less_than")
    try:
        threshold = _finite_float(condition.get("value", 0))
        price = _finite_float(stock.get("close", 0))
    except (TypeError, ValueError):
        # Inf closes would otherwise compare True for greater_than and fire alerts.
        return False
    return _compare(price, operator, threshold)


def evaluate_screening_match(condition: Dict, stock: Dict) -> bool:
    """
    Evaluate a screening condition using simple numeric thresholds.
    Supported keys: volume_threshold, min_daily_change_pct, price_min, price_max.
    """
    filters = condition.get("filters", {})
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

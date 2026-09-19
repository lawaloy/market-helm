"""Technical indicators used by alert rule evaluators."""

from __future__ import annotations

import math
from typing import Optional, Sequence


def compute_rsi(closes: Sequence[float], period: int = 14) -> Optional[float]:
    """
    Wilder RSI for the last bar in ``closes``.

    Needs at least ``period + 1`` finite closes. Returns None when the series
    is too short or RSI is undefined (no movement across the seed window).
    """
    try:
        period_n = int(period)
    except (TypeError, ValueError):
        return None
    if period_n < 2 or len(closes) < period_n + 1:
        return None

    series: list[float] = []
    for raw in closes:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value):
            return None
        series.append(value)

    changes = [series[i] - series[i - 1] for i in range(1, len(series))]
    seed = changes[:period_n]
    avg_gain = sum(max(delta, 0.0) for delta in seed) / period_n
    avg_loss = sum(max(-delta, 0.0) for delta in seed) / period_n

    for delta in changes[period_n:]:
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = ((avg_gain * (period_n - 1)) + gain) / period_n
        avg_loss = ((avg_loss * (period_n - 1)) + loss) / period_n

    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else None
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    if not math.isfinite(rsi):
        return None
    return rsi

"""Ticker symbol normalization helpers."""

from __future__ import annotations

import math
from typing import Any, Optional

# Sentinels produced when None / NaN / Inf / NA leak through str(...).upper().
_INVALID_TICKERS = frozenset(
    {"", "NAN", "NONE", "NAT", "NULL", "<NA>", "INF", "-INF", "INFINITY", "-INFINITY"}
)


def normalize_ticker(raw: Any) -> Optional[str]:
    """
    Return a stripped uppercase ticker, or None when the value is blank / missing.

    Guards against pandas NaN / Inf / None stringifying into fake tickers like
    \"NAN\" / \"INF\" / \"NONE\".
    """
    if raw is None:
        return None
    if isinstance(raw, float) and not math.isfinite(raw):
        return None
    text = str(raw).strip().upper()
    if text in _INVALID_TICKERS:
        return None
    return text

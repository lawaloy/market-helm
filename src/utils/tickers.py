"""Ticker symbol normalization helpers."""

from __future__ import annotations

import math
import re
from typing import Any, Optional

# Sentinels produced when None / NaN / Inf / NA leak through str(...).upper().
_INVALID_TICKERS = frozenset(
    {"", "NAN", "NONE", "NAT", "NULL", "<NA>", "INF", "-INF", "INFINITY", "-INFINITY"}
)
# US equity symbols stay short; reject path-like / oversized tokens before quotes/storage.
_MAX_TICKER_LEN = 16
_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,15}$")


def normalize_ticker(raw: Any) -> Optional[str]:
    """
    Return a stripped uppercase ticker, or None when the value is blank / missing.

    Guards against pandas NaN / Inf / None stringifying into fake tickers like
    \"NAN\" / \"INF\" / \"NONE\". Also rejects oversized or punctuation-heavy
    strings so they cannot reach Finnhub quotes or alert watches.
    """
    if raw is None:
        return None
    if isinstance(raw, float) and not math.isfinite(raw):
        return None
    text = str(raw).strip().upper()
    if text in _INVALID_TICKERS:
        return None
    if len(text) > _MAX_TICKER_LEN or not _TICKER_RE.fullmatch(text):
        return None
    return text

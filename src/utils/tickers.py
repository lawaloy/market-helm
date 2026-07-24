"""Ticker symbol normalization helpers."""

from __future__ import annotations

import math
from typing import Any, Optional

# Sentinels produced when None / NaN / NA leak through str(...).upper().
_INVALID_TICKERS = frozenset({"", "NAN", "NONE", "NAT", "NULL", "<NA>"})


def normalize_ticker(raw: Any) -> Optional[str]:
    """
    Return a stripped uppercase ticker, or None when the value is blank / missing.

    Guards against pandas NaN / None stringifying into fake tickers like \"NAN\" / \"NONE\".
    """
    if raw is None:
        return None
    if isinstance(raw, float) and math.isnan(raw):
        return None
    text = str(raw).strip().upper()
    if text in _INVALID_TICKERS:
        return None
    return text

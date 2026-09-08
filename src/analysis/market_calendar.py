"""Trading-session date helpers for projection horizons."""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Optional, Union

import exchange_calendars as exchange_calendars
import pandas as pd

DateLike = Union[str, date, datetime]
DEFAULT_CALENDAR = "XNYS"


def _date_text(value: DateLike) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date().isoformat()


@lru_cache(maxsize=8)
def get_market_calendar(name: str = DEFAULT_CALENDAR):
    """Return a cached exchange calendar by ISO-10383 code or supported alias."""
    try:
        return exchange_calendars.get_calendar(name)
    except Exception as exc:
        raise ValueError(f"unknown or unavailable market calendar: {name}") from exc


@lru_cache(maxsize=512)
def trading_session_after(
    value: DateLike,
    sessions: int = 5,
    calendar_name: str = DEFAULT_CALENDAR,
) -> date:
    """Return the session ``sessions`` places after the session at/before value.

    Projection runs made on a non-session day are anchored to the preceding
    session. The starting session is not counted in the horizon.
    """
    if sessions < 1:
        raise ValueError("sessions must be at least 1")
    calendar = get_market_calendar(calendar_name)
    anchor = calendar.date_to_session(_date_text(value), direction="previous")
    return calendar.sessions_window(anchor, sessions + 1)[-1].date()


def last_completed_session(
    value: datetime,
    calendar_name: str = DEFAULT_CALENDAR,
) -> date:
    """Return the most recent session whose close is at or before ``value``."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    calendar = get_market_calendar(calendar_name)
    timestamp = pd.Timestamp(value).tz_convert("UTC")
    local_date = timestamp.tz_convert(calendar.tz).date().isoformat()
    candidate = calendar.date_to_session(local_date, direction="previous")
    if calendar.session_close(candidate) <= timestamp:
        return candidate.date()
    return calendar.previous_session(candidate).date()


def completed_session_for_quote(
    value: datetime,
    calendar_name: str = DEFAULT_CALENDAR,
) -> Optional[date]:
    """Return the session closed at ``value``, or ``None`` for an intraday tick.

    Quote timestamps describe the price observation, not when MarketHelm fetched
    it. A timestamp on a weekend, holiday, or before the session close must not
    be relabeled as that calendar day's official close.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    calendar = get_market_calendar(calendar_name)
    timestamp = pd.Timestamp(value).tz_convert("UTC")
    local_date = timestamp.tz_convert(calendar.tz).date().isoformat()
    try:
        candidate = calendar.date_to_session(local_date, direction="none")
    except ValueError:
        return None
    return candidate.date() if calendar.session_close(candidate) <= timestamp else None


def trading_session_after_timestamp(
    value: datetime,
    sessions: int = 5,
    calendar_name: str = DEFAULT_CALENDAR,
) -> date:
    """Return a horizon measured from the last session completed at ``value``."""
    anchor = last_completed_session(value, calendar_name)
    return trading_session_after(anchor, sessions, calendar_name)

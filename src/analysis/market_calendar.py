"""Trading-session date helpers for projection horizons."""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Union

import exchange_calendars as exchange_calendars

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

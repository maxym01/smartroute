"""Application time zone.

Naive datetimes sent by the client (e.g. ``2026-11-12T08:00``) are read as Gdańsk local
time. Requires the ``tzdata`` package on Windows (no system time zone database).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

LOCAL_TIMEZONE_NAME = "Europe/Warsaw"
LOCAL_TIMEZONE = ZoneInfo(LOCAL_TIMEZONE_NAME)


def as_local_aware(value: datetime) -> datetime:
    """Attach Europe/Warsaw to a naive datetime. An aware datetime is returned unchanged."""
    return value.replace(tzinfo=LOCAL_TIMEZONE) if value.tzinfo is None else value

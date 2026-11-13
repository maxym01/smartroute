"""GTFS time: hours >= 24, service day and time zone.

GTFS specification: stop_times are measured from "noon minus 12 h" of the service day in
agency_timezone. That is usually midnight, but on DST change days it differs by an hour,
so the reference point is computed via UTC rather than with local-time arithmetic.
"""

import re
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

_TIME_RE = re.compile(r"^\s*(\d{1,3}):([0-5]\d):([0-5]\d)\s*$")
# Safe upper limit (2 days) — night trips in practice end before ~30:00.
MAX_GTFS_SECONDS = 48 * 3600


def parse_gtfs_time(value: str) -> int:
    """``"24:05:00"`` → 86700. Raises ``ValueError`` for an invalid format."""
    match = _TIME_RE.match(value)
    if not match:
        raise ValueError(f"Nieprawidłowy czas GTFS: {value!r}")
    hours, minutes, seconds = (int(part) for part in match.groups())
    total = hours * 3600 + minutes * 60 + seconds
    if total > MAX_GTFS_SECONDS:
        raise ValueError(f"Czas GTFS poza zakresem 0–48 h: {value!r}")
    return total


def parse_gtfs_date(value: str) -> int:
    """``"20261112"`` → 20261112 (after checking that it is a real date)."""
    value = value.strip()
    datetime.strptime(value, "%Y%m%d")  # ValueError for an invalid date
    return int(value)


def date_to_int(day: date) -> int:
    return day.year * 10000 + day.month * 100 + day.day


def int_to_date(value: int) -> date:
    return date(value // 10000, value // 100 % 100, value % 100)


def service_day_reference(day: date, tz: ZoneInfo) -> datetime:
    """The instant (UTC) from which GTFS times are measured for the service day ``day``."""
    noon_utc = datetime(day.year, day.month, day.day, 12, tzinfo=tz).astimezone(UTC)
    return noon_utc - timedelta(hours=12)


def gtfs_time_to_datetime(day: date, seconds: int, tz: ZoneInfo) -> datetime:
    """GTFS time of a service day → aware datetime in the ``tz`` time zone."""
    return (service_day_reference(day, tz) + timedelta(seconds=seconds)).astimezone(tz)

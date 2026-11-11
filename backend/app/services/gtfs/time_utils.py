"""Czas w GTFS: godziny >= 24, dzień kursowania i strefa czasowa.

Specyfikacja GTFS: czas w stop_times liczony jest od „południa minus 12 h” dnia kursowania
w strefie agency_timezone. Zwykle to północ, ale w dniach zmiany czasu (DST) różni się o godzinę,
dlatego punkt odniesienia liczymy przez UTC, a nie przez arytmetykę na czasie lokalnym.
"""

import re
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

_TIME_RE = re.compile(r"^\s*(\d{1,3}):([0-5]\d):([0-5]\d)\s*$")
# Bezpieczny górny limit (2 doby) — kursy nocne w praktyce kończą się przed ~30:00.
MAX_GTFS_SECONDS = 48 * 3600


def parse_gtfs_time(value: str) -> int:
    """``"24:05:00"`` → 86700. Rzuca ``ValueError`` dla nieprawidłowego formatu."""
    match = _TIME_RE.match(value)
    if not match:
        raise ValueError(f"Nieprawidłowy czas GTFS: {value!r}")
    hours, minutes, seconds = (int(part) for part in match.groups())
    total = hours * 3600 + minutes * 60 + seconds
    if total > MAX_GTFS_SECONDS:
        raise ValueError(f"Czas GTFS poza zakresem 0–48 h: {value!r}")
    return total


def parse_gtfs_date(value: str) -> int:
    """``"20261112"`` → 20261112 (po walidacji, że to prawdziwa data)."""
    value = value.strip()
    datetime.strptime(value, "%Y%m%d")  # ValueError dla złej daty
    return int(value)


def date_to_int(day: date) -> int:
    return day.year * 10000 + day.month * 100 + day.day


def int_to_date(value: int) -> date:
    return date(value // 10000, value // 100 % 100, value % 100)


def service_day_reference(day: date, tz: ZoneInfo) -> datetime:
    """Chwila (UTC), od której liczone są czasy GTFS dla dnia kursowania ``day``."""
    noon_utc = datetime(day.year, day.month, day.day, 12, tzinfo=tz).astimezone(UTC)
    return noon_utc - timedelta(hours=12)


def gtfs_time_to_datetime(day: date, seconds: int, tz: ZoneInfo) -> datetime:
    """Czas GTFS dnia kursowania → świadoma data w strefie ``tz``."""
    return (service_day_reference(day, tz) + timedelta(seconds=seconds)).astimezone(tz)

from datetime import UTC, date, datetime

import pytest

from app.core.timezone import LOCAL_TIMEZONE
from app.services.gtfs.text import fold_text
from app.services.gtfs.time_utils import (
    gtfs_time_to_datetime,
    parse_gtfs_date,
    parse_gtfs_time,
    service_day_reference,
)


@pytest.mark.parametrize(
    ("value", "seconds"),
    [
        ("00:00:00", 0),
        ("8:05:30", 29130),
        ("23:59:59", 86399),
        ("24:05:00", 86700),
        ("29:25:00", 105900),
    ],
)
def test_parse_gtfs_time_accepts_hours_over_24(value: str, seconds: int) -> None:
    assert parse_gtfs_time(value) == seconds


@pytest.mark.parametrize("value", ["", "8:00", "08:60:00", "08:00:61", "ab:cd:ef", "49:00:00"])
def test_parse_gtfs_time_rejects_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        parse_gtfs_time(value)


def test_parse_gtfs_date() -> None:
    assert parse_gtfs_date("20261112") == 20261112
    with pytest.raises(ValueError):
        parse_gtfs_date("20261399")


def test_after_midnight_time_maps_to_next_calendar_day() -> None:
    result = gtfs_time_to_datetime(date(2026, 11, 12), parse_gtfs_time("24:20:00"), LOCAL_TIMEZONE)

    assert result == datetime(2026, 11, 13, 0, 20, tzinfo=LOCAL_TIMEZONE)
    assert result.utcoffset().total_seconds() == 3600  # CET


def test_service_day_reference_is_local_midnight_on_normal_day() -> None:
    assert service_day_reference(date(2026, 11, 12), LOCAL_TIMEZONE) == datetime(
        2026, 11, 11, 23, 0, tzinfo=UTC
    )


def test_service_day_reference_on_dst_change_is_noon_minus_12h() -> None:
    # 29.03.2026: zmiana czasu na letni. Południe CEST = 10:00 UTC → odniesienie 22:00 UTC dnia
    # poprzedniego (czyli 23:00 CET), a nie lokalna północ.
    assert service_day_reference(date(2026, 3, 29), LOCAL_TIMEZONE) == datetime(
        2026, 3, 28, 22, 0, tzinfo=UTC
    )
    # 08:00:00 w rozkładzie tego dnia to nadal 08:00 czasu lokalnego (CEST).
    assert gtfs_time_to_datetime(date(2026, 3, 29), 8 * 3600, LOCAL_TIMEZONE) == datetime(
        2026, 3, 29, 8, 0, tzinfo=LOCAL_TIMEZONE
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [("Dworzec Główny 01", "dworzec glowny 01"), ("ŁĄKOWA", "lakowa"), (" Żabianka ", "zabianka")],
)
def test_fold_text_removes_case_and_polish_diacritics(value: str, expected: str) -> None:
    assert fold_text(value) == expected

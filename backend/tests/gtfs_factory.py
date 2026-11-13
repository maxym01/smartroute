"""Small synthetic GTFS feed for offline tests (no network).

Network: tram line 8 (A1 → B1 → C1, trip T1 and return trip T2) on weekdays 12–13.11.2026
and night line N1 (T3: A1 23:50 → B1 24:05 → C1 24:20) only on the 12.11.2026 calendar.
Stop D1 has no connections. There is only calendar_dates.txt (as in ZTM Gdańsk),
and some rows are deliberately malformed.
"""

import zipfile
from pathlib import Path

DEFAULT_FILES: dict[str, str] = {
    "agency.txt": (
        "agency_id,agency_name,agency_url,agency_timezone\n"
        "0,ZTM Test,https://example.test,Europe/Warsaw\n"
    ),
    "feed_info.txt": (
        "feed_publisher_name,feed_publisher_url,feed_lang,feed_start_date,feed_end_date\n"
        "Test,https://example.test,pl,,20261115\n"
    ),
    "stops.txt": (
        "stop_id,stop_name,stop_lat,stop_lon,stop_code\n"
        "A1,Dworzec Główny 01,54.355,18.645,A1\n"
        "B1,Brama Wyżynna 01,54.350,18.640,B1\n"
        "C1,Łąkowa 01,54.345,18.660,C1\n"
        "D1,Zaspa 01,54.390,18.600,D1\n"
    ),
    "routes.txt": (
        "route_id,agency_id,route_short_name,route_long_name,route_type\n"
        "R8,0,8,,900\n"
        "RN,0,N1,,700\n"
    ),
    # CRLF as in the real ZTM feed; the last row has an invalid date.
    "calendar_dates.txt": (
        "service_id,date,exception_type\r\n"
        "WD,20261112,1\r\n"
        "WD,20261113,1\r\n"
        "NIGHT,20261112,1\r\n"
        "BAD,20261399,1\r\n"
    ),
    "trips.txt": (
        "route_id,service_id,trip_id,trip_headsign,direction_id\n"
        "R8,WD,T1,Łąkowa,0\n"
        "R8,WD,T2,Dworzec Główny,1\n"
        "RN,NIGHT,T3,Łąkowa,0\n"
        "RX,WD,TBAD,Nieznana linia,0\n"
    ),
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type\n"
        "T1,08:00:00,08:00:00,A1,1,0,1\n"
        "T1,08:10:00,08:10:00,B1,2,0,0\n"
        "T1,08:20:00,08:20:00,C1,3,1,0\n"
        "T1,25:61:00,25:61:00,D1,4,0,0\n"
        "T2,09:00:00,09:00:00,C1,1,0,1\n"
        "T2,09:10:00,09:10:00,B1,2,0,0\n"
        "T2,09:20:00,09:20:00,A1,3,1,0\n"
        "T3,23:50:00,23:50:00,A1,1,0,1\n"
        "T3,24:05:00,24:05:00,B1,2,0,0\n"
        "T3,24:20:00,24:20:00,C1,3,1,0\n"
        "TBAD,10:00:00,10:00:00,A1,1,0,0\n"
    ),
}


def build_gtfs_zip(
    path: Path,
    *,
    overrides: dict[str, str] | None = None,
    drop: set[str] | frozenset[str] = frozenset(),
    extra_members: dict[str, str] | None = None,
) -> Path:
    files = {**DEFAULT_FILES, **(overrides or {})}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            if name not in drop:
                archive.writestr(name, content.encode("utf-8"))
        for name, content in (extra_members or {}).items():
            archive.writestr(name, content.encode("utf-8"))
    return path

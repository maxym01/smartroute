"""Import GTFS Static (ZIP z URL lub z dysku) do bazy SQLite rozkładu.

Założenia:
- **Pamięć:** pliki CSV są czytane strumieniowo prosto z ZIP-a (bez rozpakowywania na dysk)
  i wstawiane partiami. W pamięci trzymamy tylko słowniki identyfikatorów (przystanki, kursy,
  usługi), a nie stop_times.
- **Transakcja:** cały import (DROP + CREATE + INSERT) to jedna transakcja SQLite. Błąd w trakcie
  oznacza ROLLBACK, a poprzedni rozkład zostaje nietknięty. Dzięki WAL API czyta stare dane do
  chwili COMMIT. Ponowny import w całości zastępuje poprzedni.
- **Bezpieczny ZIP:** czytamy wyłącznie znane pliki z katalogu głównego archiwum (nic nie jest
  rozpakowywane, więc nie ma ryzyka zip-slip), odrzucamy pliki zaszyfrowane, zbyt duże
  i o podejrzanym współczynniku kompresji (zip bomb). ``zipfile`` nie odczyta więcej bajtów niż
  zadeklarowany rozmiar, więc limit dotyczy faktycznie przeczytanych danych.
- **Kalendarz:** obsługiwane są calendar.txt i/lub calendar_dates.txt (ZTM Gdańsk publikuje
  tylko calendar_dates.txt z ``exception_type=1``).
- **Wadliwe wiersze** (zły format czasu, nieznany kurs/przystanek itp.) są pomijane i liczone
  w raporcie. Brak wymaganego pliku lub kolumny przerywa import.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import tempfile
import time
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Connection, Engine, func, insert, select

from app.core.timezone import LOCAL_TIMEZONE_NAME
from app.db.gtfs_session import build_gtfs_engine
from app.models.gtfs import (
    GtfsBase,
    GtfsFeed,
    GtfsRoute,
    GtfsServiceDate,
    GtfsStop,
    GtfsStopTime,
    GtfsTrip,
)
from app.services.gtfs.text import fold_text
from app.services.gtfs.time_utils import (
    date_to_int,
    int_to_date,
    parse_gtfs_date,
    parse_gtfs_time,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 10_000
MAX_MEMBER_BYTES = 1024 * 1024 * 1024  # 1 GiB po rozpakowaniu na plik
MAX_COMPRESSION_RATIO = 100
MAX_WARNINGS = 20
USER_AGENT = "SmartRoute-GTFS-Importer/0.1"

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "stops.txt": ("stop_id", "stop_name"),
    "routes.txt": ("route_id", "route_type"),
    "trips.txt": ("route_id", "service_id", "trip_id"),
    "stop_times.txt": ("trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"),
    "calendar.txt": (
        "service_id",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "start_date",
        "end_date",
    ),
    "calendar_dates.txt": ("service_id", "date", "exception_type"),
}
REQUIRED_FILES = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")
CALENDAR_FILES = ("calendar.txt", "calendar_dates.txt")
OPTIONAL_FILES = ("agency.txt", "feed_info.txt")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class GtfsImportError(Exception):
    """Błąd, który przerywa import (poprzednie dane pozostają bez zmian)."""


@dataclass
class ImportReport:
    source: str
    sha256: str = ""
    timezone: str = LOCAL_TIMEZONE_NAME
    valid_from: int | None = None
    valid_to: int | None = None
    counts: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    duration_s: float = 0.0

    @property
    def skipped_total(self) -> int:
        return sum(self.skipped.values())

    def skip(self, file: str, message: str) -> None:
        self.skipped[file] = self.skipped.get(file, 0) + 1
        if len(self.warnings) < MAX_WARNINGS:
            self.warnings.append(f"{file}: {message}")


# --- Źródło: URL albo plik ------------------------------------------------------------------


def is_url(source: str) -> bool:
    return urlparse(source).scheme in ("http", "https")


def download(url: str, destination: Path, *, max_bytes: int, timeout_s: float = 60) -> None:
    if not is_url(url):
        raise GtfsImportError(f"Obsługiwane są tylko adresy http(s): {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    received = 0
    try:
        with (
            urllib.request.urlopen(request, timeout=timeout_s) as response,
            destination.open("wb") as out,
        ):
            declared = response.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise GtfsImportError(
                    f"Plik ma {int(declared) / 1e6:.0f} MB, limit to {max_bytes / 1e6:.0f} MB"
                )
            while chunk := response.read(1024 * 1024):
                received += len(chunk)
                if received > max_bytes:
                    raise GtfsImportError(f"Pobierany plik przekracza {max_bytes / 1e6:.0f} MB")
                out.write(chunk)
    except GtfsImportError:
        raise
    except OSError as exc:  # URLError, HTTPError, timeout
        raise GtfsImportError(f"Nie udało się pobrać {url}: {exc}") from exc
    logger.info("Pobrano %.1f MB z %s", received / 1e6, url)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


# --- ZIP i CSV ------------------------------------------------------------------------------


class GtfsArchive:
    """Bezpieczny dostęp tylko do znanych plików GTFS w katalogu głównym archiwum."""

    def __init__(self, path: Path, *, max_member_bytes: int = MAX_MEMBER_BYTES) -> None:
        if not zipfile.is_zipfile(path):
            raise GtfsImportError(f"{path} nie jest prawidłowym archiwum ZIP")
        self.zip = zipfile.ZipFile(path)
        known = set(REQUIRED_COLUMNS) | set(OPTIONAL_FILES)
        # Tylko nazwy bez katalogów — "../stops.txt" czy "x/stops.txt" są ignorowane.
        self.members = {
            info.filename: info for info in self.zip.infolist() if info.filename in known
        }
        for info in self.members.values():
            self._check_member(info, max_member_bytes)

    @staticmethod
    def _check_member(info: zipfile.ZipInfo, max_bytes: int) -> None:
        if info.flag_bits & 0x1:
            raise GtfsImportError(f"{info.filename}: zaszyfrowane pliki nie są obsługiwane")
        if info.file_size > max_bytes:
            raise GtfsImportError(
                f"{info.filename}: {info.file_size} B po rozpakowaniu "
                f"przekracza limit {max_bytes} B"
            )
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise GtfsImportError(f"{info.filename}: podejrzany współczynnik kompresji")

    def __enter__(self) -> GtfsArchive:
        return self

    def __exit__(self, *_: object) -> None:
        self.zip.close()

    def has(self, name: str) -> bool:
        return name in self.members

    def header(self, name: str) -> list[str]:
        with self._text(name) as f:
            return [column.strip() for column in next(csv.reader(f), [])]

    def rows(self, name: str) -> Iterator[tuple[int, dict[str, str]]]:
        """Wiersze jako słowniki (nr linii, dane). Wartości przycięte; brak kolumny → ""."""
        with self._text(name) as f:
            reader = csv.reader(f)
            header = [column.strip() for column in next(reader, [])]
            for line_no, values in enumerate(reader, start=2):
                if not values or values == [""]:
                    continue
                yield (
                    line_no,
                    {
                        key: (values[i].strip() if i < len(values) else "")
                        for i, key in enumerate(header)
                    },
                )

    def _text(self, name: str) -> io.TextIOWrapper:
        # utf-8-sig: toleruje BOM; newline="" — csv sam obsługuje CRLF.
        return io.TextIOWrapper(self.zip.open(self.members[name]), encoding="utf-8-sig", newline="")


def validate_structure(archive: GtfsArchive) -> None:
    missing = [name for name in REQUIRED_FILES if not archive.has(name)]
    if not any(archive.has(name) for name in CALENDAR_FILES):
        missing.append("calendar.txt lub calendar_dates.txt")
    if missing:
        raise GtfsImportError(f"Brak wymaganych plików GTFS: {', '.join(missing)}")
    for name, columns in REQUIRED_COLUMNS.items():
        if not archive.has(name):
            continue
        try:
            header = archive.header(name)
        except UnicodeDecodeError as exc:
            raise GtfsImportError(f"{name}: plik nie jest w UTF-8") from exc
        absent = [column for column in columns if column not in header]
        if absent:
            raise GtfsImportError(f"{name}: brak wymaganych kolumn: {', '.join(absent)}")


# --- Import ---------------------------------------------------------------------------------


class _BatchInserter:
    def __init__(self, conn: Connection, table: Any, *, or_ignore: bool = False) -> None:
        self.conn, self.batch, self.count = conn, [], 0
        self.statement = insert(table).prefix_with("OR IGNORE") if or_ignore else insert(table)

    def add(self, row: dict[str, Any]) -> None:
        self.batch.append(row)
        if len(self.batch) >= BATCH_SIZE:
            self.flush()

    def flush(self) -> None:
        if self.batch:
            self.conn.execute(self.statement, self.batch)
            self.count += len(self.batch)
            self.batch = []


def _optional_int(value: str, default: int | None = None) -> int | None:
    return int(value) if value else default


def _optional_float(value: str) -> float | None:
    return float(value) if value else None


def _read_timezone(archive: GtfsArchive, report: ImportReport) -> None:
    name = ""
    if archive.has("agency.txt"):
        name = next((row.get("agency_timezone", "") for _, row in archive.rows("agency.txt")), "")
    name = name or LOCAL_TIMEZONE_NAME
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise GtfsImportError(f"agency.txt: nieznana strefa czasowa {name!r}") from exc
    report.timezone = name


def _read_feed_validity(archive: GtfsArchive) -> tuple[int | None, int | None]:
    if not archive.has("feed_info.txt"):
        return None, None
    for _, row in archive.rows("feed_info.txt"):
        try:
            start = parse_gtfs_date(row["feed_start_date"]) if row.get("feed_start_date") else None
            end = parse_gtfs_date(row["feed_end_date"]) if row.get("feed_end_date") else None
        except ValueError:
            return None, None
        return start, end
    return None, None


def _load_service_dates(archive: GtfsArchive, report: ImportReport) -> set[tuple[str, int]]:
    active: set[tuple[str, int]] = set()
    if archive.has("calendar.txt"):
        for line, row in archive.rows("calendar.txt"):
            try:
                start = int_to_date(parse_gtfs_date(row["start_date"]))
                end = int_to_date(parse_gtfs_date(row["end_date"]))
                days = [row[day] == "1" for day in WEEKDAYS]
                if not row["service_id"] or end < start or (end - start).days > 3660:
                    raise ValueError("nieprawidłowy zakres dat lub service_id")
            except (ValueError, KeyError) as exc:
                report.skip("calendar.txt", f"linia {line}: {exc}")
                continue
            day = start
            while day <= end:
                if days[day.weekday()]:
                    active.add((row["service_id"], date_to_int(day)))
                day += timedelta(days=1)
    if archive.has("calendar_dates.txt"):
        for line, row in archive.rows("calendar_dates.txt"):
            try:
                key = (row["service_id"], parse_gtfs_date(row["date"]))
                if not key[0] or row["exception_type"] not in ("1", "2"):
                    raise ValueError("exception_type musi być 1 lub 2")
            except ValueError as exc:
                report.skip("calendar_dates.txt", f"linia {line}: {exc}")
                continue
            if row["exception_type"] == "1":
                active.add(key)
            else:
                active.discard(key)
    return active


def _import_into(conn: Connection, archive: GtfsArchive, report: ImportReport) -> None:
    _read_timezone(archive, report)
    feed_start, feed_end = _read_feed_validity(archive)

    # Atomowa podmiana: stare tabele znikają dopiero przy COMMIT.
    GtfsBase.metadata.drop_all(conn)
    GtfsBase.metadata.create_all(conn)
    # Indeks pomocniczy budujemy po wstawieniu danych — tak jest wielokrotnie szybciej.
    deferred_indexes = list(GtfsStopTime.__table__.indexes)
    for index in deferred_indexes:
        index.drop(conn)

    # stops
    stops = _BatchInserter(conn, GtfsStop.__table__)
    stop_ids: set[str] = set()
    for line, row in archive.rows("stops.txt"):
        try:
            if not row["stop_id"] or not row["stop_name"]:
                raise ValueError("brak stop_id lub stop_name")
            if row.get("location_type", "") not in ("", "0"):
                continue  # stacje/wejścia — połączenia dotyczą tylko słupków (location_type=0)
            if row["stop_id"] in stop_ids:
                raise ValueError(f"zduplikowany stop_id {row['stop_id']}")
            stops.add(
                {
                    "stop_id": row["stop_id"],
                    "stop_name": row["stop_name"],
                    "stop_code": row.get("stop_code") or None,
                    "stop_lat": _optional_float(row.get("stop_lat", "")),
                    "stop_lon": _optional_float(row.get("stop_lon", "")),
                    "search_name": fold_text(row["stop_name"]),
                }
            )
            stop_ids.add(row["stop_id"])
        except ValueError as exc:
            report.skip("stops.txt", f"linia {line}: {exc}")
    stops.flush()

    # routes
    routes = _BatchInserter(conn, GtfsRoute.__table__)
    route_ids: set[str] = set()
    for line, row in archive.rows("routes.txt"):
        try:
            if not row["route_id"] or row["route_id"] in route_ids:
                raise ValueError("brak lub duplikat route_id")
            routes.add(
                {
                    "route_id": row["route_id"],
                    "short_name": row.get("route_short_name") or None,
                    "long_name": row.get("route_long_name") or None,
                    "route_type": int(row["route_type"]),
                }
            )
            route_ids.add(row["route_id"])
        except ValueError as exc:
            report.skip("routes.txt", f"linia {line}: {exc}")
    routes.flush()

    # kalendarz
    service_dates = _load_service_dates(archive, report)
    active_services = {service_id for service_id, _ in service_dates}
    dates_table = _BatchInserter(conn, GtfsServiceDate.__table__)
    for service_id, day in sorted(service_dates):
        dates_table.add({"service_id": service_id, "date": day})
    dates_table.flush()

    # trips
    trips = _BatchInserter(conn, GtfsTrip.__table__)
    trip_pks: dict[str, int] = {}
    for line, row in archive.rows("trips.txt"):
        try:
            if not row["trip_id"] or row["trip_id"] in trip_pks:
                raise ValueError("brak lub duplikat trip_id")
            if row["route_id"] not in route_ids:
                raise ValueError(f"nieznana linia route_id={row['route_id']}")
            if row["service_id"] not in active_services:
                # Kurs bez żadnego dnia kursowania nie wpływa na wyniki — pomijamy.
                report.skip("trips.txt", f"linia {line}: usługa bez dni kursowania")
                continue
            pk = len(trip_pks) + 1
            trips.add(
                {
                    "id": pk,
                    "trip_id": row["trip_id"],
                    "route_id": row["route_id"],
                    "service_id": row["service_id"],
                    "headsign": row.get("trip_headsign") or None,
                    "direction_id": _optional_int(row.get("direction_id", "")),
                }
            )
            trip_pks[row["trip_id"]] = pk
        except ValueError as exc:
            report.skip("trips.txt", f"linia {line}: {exc}")
    trips.flush()

    # stop_times (największy plik — strumieniowo)
    # Duplikaty (trip, stop_sequence) wykrywamy w obrębie bieżącego kursu (pliki zwykle są
    # pogrupowane po trip_id); rzadkie duplikaty rozproszone odrzuci INSERT OR IGNORE na PK.
    # Globalny zbiór dla milionów wierszy zużywałby setki MB pamięci.
    stop_times = _BatchInserter(conn, GtfsStopTime.__table__, or_ignore=True)
    current_trip: int | None = None
    seen: set[int] = set()
    max_secs = 0
    for line, row in archive.rows("stop_times.txt"):
        try:
            trip_pk = trip_pks.get(row["trip_id"])
            if trip_pk is None:
                raise ValueError(f"nieznany lub pominięty kurs trip_id={row['trip_id']}")
            if row["stop_id"] not in stop_ids:
                raise ValueError(f"nieznany przystanek stop_id={row['stop_id']}")
            arrival, departure = row["arrival_time"], row["departure_time"]
            if not arrival and not departure:
                raise ValueError("brak czasu przyjazdu i odjazdu (interpolacja nieobsługiwana)")
            arrival_secs = parse_gtfs_time(arrival or departure)
            departure_secs = parse_gtfs_time(departure or arrival)
            if departure_secs < arrival_secs:
                raise ValueError("odjazd przed przyjazdem")
            sequence = int(row["stop_sequence"])
            if trip_pk != current_trip:
                current_trip, seen = trip_pk, set()
            if sequence in seen:
                raise ValueError("zduplikowane stop_sequence w kursie")
            seen.add(sequence)
            stop_times.add(
                {
                    "trip_pk": trip_pk,
                    "stop_sequence": sequence,
                    "stop_id": row["stop_id"],
                    "arrival_secs": arrival_secs,
                    "departure_secs": departure_secs,
                    "pickup_type": _optional_int(row.get("pickup_type", ""), 0),
                    "drop_off_type": _optional_int(row.get("drop_off_type", ""), 0),
                }
            )
            max_secs = max(max_secs, arrival_secs, departure_secs)
        except ValueError as exc:
            report.skip("stop_times.txt", f"linia {line}: {exc}")
    stop_times.flush()

    if not trips.count or not stop_times.count:
        raise GtfsImportError("Po walidacji nie zostały żadne kursy lub czasy przejazdu")

    logger.info("Budowanie indeksów…")
    for index in deferred_indexes:
        index.create(conn)

    # INSERT OR IGNORE mógł odrzucić duplikaty — liczymy faktycznie zapisane wiersze.
    stop_times_saved = conn.scalar(select(func.count()).select_from(GtfsStopTime.__table__)) or 0
    dates = [day for _, day in service_dates]
    report.valid_from = feed_start or (min(dates) if dates else None)
    report.valid_to = feed_end or (max(dates) if dates else None)
    report.counts = {
        "stops": stops.count,
        "routes": routes.count,
        "trips": trips.count,
        "stop_times": stop_times_saved,
        "service_dates": dates_table.count,
    }
    conn.execute(
        insert(GtfsFeed.__table__),
        {
            "id": 1,
            "source": report.source[:1000],
            "sha256": report.sha256,
            "imported_at": datetime.now(UTC).replace(tzinfo=None),
            "timezone": report.timezone,
            "valid_from": report.valid_from,
            "valid_to": report.valid_to,
            "max_time_secs": max_secs,
            "stops_count": stops.count,
            "routes_count": routes.count,
            "trips_count": trips.count,
            "stop_times_count": stop_times_saved,
            "service_dates_count": dates_table.count,
            "skipped_rows": report.skipped_total,
        },
    )


def import_zip(
    zip_path: Path,
    engine: Engine,
    *,
    source: str | None = None,
    max_member_bytes: int = MAX_MEMBER_BYTES,
) -> ImportReport:
    """Importuje lokalny ZIP do bazy ``engine`` w jednej transakcji."""
    started = time.perf_counter()
    report = ImportReport(source=source or str(zip_path))
    report.sha256 = sha256_of(zip_path)
    with GtfsArchive(zip_path, max_member_bytes=max_member_bytes) as archive:
        validate_structure(archive)
        try:
            with engine.begin() as conn:
                _import_into(conn, archive, report)
        except (UnicodeDecodeError, csv.Error, zipfile.BadZipFile) as exc:
            raise GtfsImportError(f"Nie udało się odczytać pliku CSV: {exc}") from exc
    report.duration_s = time.perf_counter() - started
    return report


def import_gtfs(
    source: str,
    database_url: str,
    *,
    max_download_mb: int = 200,
    progress: Callable[[str], None] | None = None,
) -> ImportReport:
    """Importuje z URL (pobiera do pliku tymczasowego) albo ze ścieżki do lokalnego ZIP-a."""
    say = progress or logger.info
    engine = build_gtfs_engine(database_url)
    try:
        if is_url(source):
            fd, tmp_name = tempfile.mkstemp(prefix="gtfs-", suffix=".zip")
            os.close(fd)
            tmp_path = Path(tmp_name)
            try:
                say(f"Pobieranie {source} …")
                download(source, tmp_path, max_bytes=max_download_mb * 1024 * 1024)
                say("Import do bazy …")
                return import_zip(tmp_path, engine, source=source)
            finally:
                tmp_path.unlink(missing_ok=True)
        path = Path(source)
        if not path.is_file():
            raise GtfsImportError(f"Plik nie istnieje: {path}")
        say(f"Import {path} do bazy …")
        return import_zip(path, engine, source=str(path.resolve()))
    finally:
        engine.dispose()

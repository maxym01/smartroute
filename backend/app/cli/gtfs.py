"""CLI rozkładu GTFS.

Uruchamiaj z katalogu ``backend`` (tam leży ``.env`` i domyślna baza ``gtfs.db``)::

    python -m app.cli.gtfs import                    # oficjalny URL ZTM Gdańsk (GTFS_FEED_URL)
    python -m app.cli.gtfs import --source plik.zip  # lokalny ZIP
    python -m app.cli.gtfs info                      # stan zaimportowanego rozkładu
"""

import argparse
import logging
import sys

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.gtfs_session import build_gtfs_engine, sqlite_file_exists
from app.models.gtfs import GtfsFeed
from app.services.gtfs.importer import GtfsImportError, ImportReport, import_gtfs
from app.services.gtfs.time_utils import int_to_date


def _fmt_day(value: int | None) -> str:
    return int_to_date(value).isoformat() if value else "?"


def _print_report(report: ImportReport) -> None:
    print(f"Zaimportowano rozkład w {report.duration_s:.1f} s")
    print(f"  źródło:      {report.source}")
    print(f"  sha256:      {report.sha256}")
    print(f"  strefa:      {report.timezone}")
    print(f"  ważność:     {_fmt_day(report.valid_from)} – {_fmt_day(report.valid_to)}")
    for name, count in report.counts.items():
        print(f"  {name + ':':<14}{count:>10,}".replace(",", " "))
    if report.skipped:
        print(f"  pominięte wiersze: {report.skipped_total} ({report.skipped})")
        for warning in report.warnings:
            print(f"    - {warning}")


def _cmd_import(args: argparse.Namespace) -> int:
    settings = get_settings()
    source = args.source or settings.gtfs_feed_url
    database_url = args.database_url or settings.gtfs_database_url
    try:
        report = import_gtfs(
            source,
            database_url,
            max_download_mb=settings.gtfs_max_download_mb,
            progress=print,
        )
    except GtfsImportError as exc:
        print(f"BŁĄD importu: {exc}", file=sys.stderr)
        print("Poprzedni rozkład (jeśli był) pozostał bez zmian.", file=sys.stderr)
        return 1
    _print_report(report)
    print(f"  baza:        {database_url}")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    database_url = args.database_url or get_settings().gtfs_database_url
    if not sqlite_file_exists(database_url):
        print(f"Rozkład nie został zaimportowany ({database_url}).")
        return 1
    engine = build_gtfs_engine(database_url)
    try:
        with engine.connect() as conn:
            feed = conn.execute(select(GtfsFeed.__table__)).mappings().first()
    except SQLAlchemyError:
        feed = None
    finally:
        engine.dispose()
    if feed is None:
        print(f"Baza {database_url} nie zawiera zaimportowanego rozkładu.")
        return 1
    print(f"Źródło:      {feed['source']}")
    print(f"Import:      {feed['imported_at']:%Y-%m-%d %H:%M} UTC")
    print(f"Ważność:     {_fmt_day(feed['valid_from'])} – {_fmt_day(feed['valid_to'])}")
    print(
        f"Dane:        {feed['stops_count']} przystanków, {feed['routes_count']} linii, "
        f"{feed['trips_count']} kursów, {feed['stop_times_count']} postojów"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.gtfs", description="Import i stan rozkładu GTFS Static"
    )
    parser.add_argument("--database-url", help="Nadpisuje GTFS_DATABASE_URL")
    commands = parser.add_subparsers(dest="command", required=True)
    import_cmd = commands.add_parser("import", help="Import GTFS Static z URL lub pliku ZIP")
    import_cmd.add_argument(
        "--source", help="URL (http/https) lub ścieżka do ZIP-a; domyślnie GTFS_FEED_URL"
    )
    import_cmd.set_defaults(handler=_cmd_import)
    info_cmd = commands.add_parser("info", help="Informacje o zaimportowanym rozkładzie")
    info_cmd.set_defaults(handler=_cmd_info)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())

import zipfile
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select, text

from app.db.gtfs_session import build_gtfs_engine
from app.models.gtfs import GtfsFeed, GtfsServiceDate, GtfsStop, GtfsStopTime, GtfsTrip
from app.services.gtfs.importer import GtfsImportError, import_gtfs, import_zip
from tests.gtfs_factory import build_gtfs_zip


def count(engine: Engine, model: type) -> int:
    with engine.connect() as conn:
        return conn.scalar(select(func.count()).select_from(model)) or 0


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = build_gtfs_engine(f"sqlite:///{tmp_path / 'gtfs.db'}")
    yield engine
    engine.dispose()


def test_import_loads_feed_with_only_calendar_dates(tmp_path: Path, engine: Engine) -> None:
    report = import_zip(build_gtfs_zip(tmp_path / "f.zip"), engine)

    assert report.counts == {
        "stops": 4,
        "routes": 2,
        "trips": 3,  # TBAD rejected (unknown route)
        "stop_times": 9,  # bad time 25:61 and the TBAD trip row rejected
        "service_dates": 3,  # BAD with an invalid date rejected
    }
    assert report.skipped == {"calendar_dates.txt": 1, "trips.txt": 1, "stop_times.txt": 2}
    assert report.timezone == "Europe/Warsaw"
    assert (report.valid_from, report.valid_to) == (20261112, 20261115)
    with engine.connect() as conn:
        feed = conn.execute(select(GtfsFeed.__table__)).mappings().one()
        dates = conn.execute(select(GtfsServiceDate.service_id, GtfsServiceDate.date)).all()
        night = (
            conn.execute(
                select(GtfsStopTime.departure_secs)
                .join(GtfsTrip, GtfsTrip.id == GtfsStopTime.trip_pk)
                .where(GtfsTrip.trip_id == "T3")
                .order_by(GtfsStopTime.stop_sequence)
            )
            .scalars()
            .all()
        )
    assert feed["max_time_secs"] == 24 * 3600 + 20 * 60
    assert sorted(dates) == [("NIGHT", 20261112), ("WD", 20261112), ("WD", 20261113)]
    assert night == [85800, 86700, 87600]  # 23:50, 24:05, 24:20


def test_calendar_txt_is_expanded_and_exceptions_applied(tmp_path: Path, engine: Engine) -> None:
    zip_path = build_gtfs_zip(
        tmp_path / "f.zip",
        overrides={
            # Mon–Fri 09–15.11.2026 (Mon 09.11) …
            "calendar.txt": (
                "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
                "start_date,end_date\n"
                "WD,1,1,1,1,1,0,0,20261109,20261115\n"
            ),
            # … without 11.11 (public holiday), with an extra Saturday 14.11.
            "calendar_dates.txt": (
                "service_id,date,exception_type\nWD,20261111,2\nWD,20261114,1\nNIGHT,20261112,1\n"
            ),
        },
    )

    import_zip(zip_path, engine)

    with engine.connect() as conn:
        wd = conn.scalars(
            select(GtfsServiceDate.date)
            .where(GtfsServiceDate.service_id == "WD")
            .order_by(GtfsServiceDate.date)
        ).all()
    assert wd == [20261109, 20261110, 20261112, 20261113, 20261114]


def test_reimport_replaces_previous_data(tmp_path: Path, engine: Engine) -> None:
    import_zip(build_gtfs_zip(tmp_path / "a.zip"), engine)
    smaller = build_gtfs_zip(
        tmp_path / "b.zip",
        overrides={
            "stops.txt": "stop_id,stop_name\nA1,Dworzec Główny 01\nB1,Brama Wyżynna 01\n",
            "trips.txt": "route_id,service_id,trip_id\nR8,WD,T1\n",
            "stop_times.txt": (
                "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                "T1,08:00:00,08:00:00,A1,1\nT1,08:10:00,08:10:00,B1,2\n"
            ),
        },
    )

    import_zip(smaller, engine)

    assert count(engine, GtfsStop) == 2
    assert count(engine, GtfsTrip) == 1
    assert count(engine, GtfsStopTime) == 2
    assert count(engine, GtfsFeed) == 1


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"drop": {"stop_times.txt"}}, "stop_times.txt"),
        ({"drop": {"calendar_dates.txt"}}, "calendar.txt lub calendar_dates.txt"),
        ({"overrides": {"stops.txt": "stop_id,name\nA1,X\n"}}, "stop_name"),
        ({"overrides": {"trips.txt": "route_id,service_id,trip_id\nRX,WD,T1\n"}}, "żadne kursy"),
    ],
)
def test_invalid_feed_fails_and_keeps_previous_data(
    tmp_path: Path, engine: Engine, kwargs: dict, message: str
) -> None:
    import_zip(build_gtfs_zip(tmp_path / "good.zip"), engine)

    with pytest.raises(GtfsImportError, match=message):
        import_zip(build_gtfs_zip(tmp_path / "bad.zip", **kwargs), engine)

    # Transaction rolled back — the previous timetable is still complete.
    assert count(engine, GtfsStop) == 4
    assert count(engine, GtfsStopTime) == 9


def test_non_zip_file_is_rejected(tmp_path: Path, engine: Engine) -> None:
    path = tmp_path / "not.zip"
    path.write_text("to nie jest zip", encoding="utf-8")

    with pytest.raises(GtfsImportError, match="ZIP"):
        import_zip(path, engine)


def test_members_outside_root_are_ignored(tmp_path: Path, engine: Engine) -> None:
    # Paths with directories (including "../") are neither read nor extracted to disk.
    zip_path = build_gtfs_zip(
        tmp_path / "f.zip",
        extra_members={"../evil.txt": "x", "nested/stops.txt": "stop_id,stop_name\nZ,Zły\n"},
    )

    import_zip(zip_path, engine)

    assert count(engine, GtfsStop) == 4
    assert not (tmp_path.parent / "evil.txt").exists()


def test_oversized_member_is_rejected(tmp_path: Path, engine: Engine) -> None:
    with pytest.raises(GtfsImportError, match="przekracza limit"):
        import_zip(build_gtfs_zip(tmp_path / "f.zip"), engine, max_member_bytes=100)


def test_suspicious_compression_ratio_is_rejected(tmp_path: Path, engine: Engine) -> None:
    # 5 MB of zeros compresses ~1000:1 — a typical sign of a "zip bomb".
    zip_path = build_gtfs_zip(tmp_path / "f.zip", overrides={"feed_info.txt": "0" * 5_000_000})
    assert zipfile.ZipFile(zip_path).getinfo("feed_info.txt").compress_size < 50_000

    with pytest.raises(GtfsImportError, match="kompresji"):
        import_zip(zip_path, engine)


def test_import_gtfs_from_missing_local_file(tmp_path: Path) -> None:
    with pytest.raises(GtfsImportError, match="nie istnieje"):
        import_gtfs(str(tmp_path / "brak.zip"), f"sqlite:///{tmp_path / 'g.db'}")


def test_import_gtfs_rejects_non_http_url(tmp_path: Path) -> None:
    from app.services.gtfs.importer import download

    with pytest.raises(GtfsImportError, match="http"):
        download("file:///etc/passwd", tmp_path / "x.zip", max_bytes=10)


def test_database_uses_wal_for_concurrent_reads(tmp_path: Path, engine: Engine) -> None:
    import_zip(build_gtfs_zip(tmp_path / "f.zip"), engine)

    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conn.execute(text("SELECT count(*) FROM gtfs_routes")).scalar() == 2

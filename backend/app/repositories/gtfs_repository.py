"""Zapytania do bazy rozkładu GTFS (tylko odczyt)."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, aliased

from app.models.gtfs import GtfsFeed, GtfsRoute, GtfsServiceDate, GtfsStop, GtfsStopTime, GtfsTrip
from app.services.gtfs.text import fold_text

# pickup_type / drop_off_type = 1 oznacza „brak możliwości wsiadania / wysiadania”.
NOT_AVAILABLE = 1


@dataclass(frozen=True, slots=True)
class ScheduledRide:
    """Surowy wynik zapytania: czasy w sekundach GTFS względem dnia kursowania."""

    trip_id: str
    route_id: str
    route_short_name: str | None
    route_long_name: str | None
    route_type: int
    headsign: str | None
    direction_id: int | None
    departure_secs: int
    arrival_secs: int
    origin_sequence: int
    destination_sequence: int


class GtfsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def feed(self) -> GtfsFeed | None:
        """Metadane importu albo ``None``, gdy baza nie zawiera rozkładu."""
        try:
            return self.session.get(GtfsFeed, 1)
        except OperationalError:  # brak tabel — import nie został wykonany
            self.session.rollback()
            return None

    def get_stop(self, stop_id: str) -> GtfsStop | None:
        return self.session.get(GtfsStop, stop_id)

    def search_stops(self, query: str, limit: int) -> Sequence[GtfsStop]:
        needle = fold_text(query)
        pattern_filter = GtfsStop.search_name.contains(needle, autoescape=True)
        exact_id = or_(GtfsStop.stop_id == query.strip(), GtfsStop.stop_code == query.strip())
        # Kolejność: dokładne ID/kod, początek nazwy, reszta — w grupie alfabetycznie.
        rank = case(
            (exact_id, 0),
            (GtfsStop.search_name.startswith(needle, autoescape=True), 1),
            else_=2,
        )
        return self.session.scalars(
            select(GtfsStop)
            .where(or_(pattern_filter, exact_id))
            # search_name, a nie stop_name: binarne sortowanie stawiałoby „Ł…” po „Z…”.
            .order_by(rank, GtfsStop.search_name, GtfsStop.stop_id)
            .limit(limit)
        ).all()

    def direct_rides(
        self,
        *,
        origin_stop_id: str,
        destination_stop_id: str,
        service_date: int,
        min_departure_secs: int,
        max_departure_secs: int,
        limit: int,
    ) -> list[ScheduledRide]:
        """Kursy bez przesiadki: odjazd z ``origin`` w oknie czasu, później ``destination``.

        Kierunek wynika z kolejności przystanków (``stop_sequence`` celu > startu), więc kurs
        w przeciwną stronę nie zostanie zwrócony. Jeśli kurs odwiedza cel kilka razy (pętla),
        bierzemy najbliższe wystąpienie.
        """
        origin = aliased(GtfsStopTime, name="origin")
        destination = aliased(GtfsStopTime, name="destination")

        first_destination_seq = (
            select(func.min(destination.stop_sequence))
            .where(
                destination.trip_pk == origin.trip_pk,
                destination.stop_sequence > origin.stop_sequence,
                destination.stop_id == destination_stop_id,
                destination.drop_off_type != NOT_AVAILABLE,
            )
            .correlate(origin)
            .scalar_subquery()
        )
        candidates = (
            select(
                origin.trip_pk.label("trip_pk"),
                origin.stop_sequence.label("origin_sequence"),
                origin.departure_secs.label("departure_secs"),
                first_destination_seq.label("destination_sequence"),
            )
            .join(GtfsTrip, GtfsTrip.id == origin.trip_pk)
            .join(
                GtfsServiceDate,
                and_(
                    GtfsServiceDate.service_id == GtfsTrip.service_id,
                    GtfsServiceDate.date == service_date,
                ),
            )
            .where(
                origin.stop_id == origin_stop_id,
                origin.departure_secs.between(min_departure_secs, max_departure_secs),
                origin.pickup_type != NOT_AVAILABLE,
            )
            .subquery()
        )
        arrival = aliased(GtfsStopTime, name="arrival")
        rows = self.session.execute(
            select(
                GtfsTrip.trip_id,
                GtfsRoute.route_id,
                GtfsRoute.short_name,
                GtfsRoute.long_name,
                GtfsRoute.route_type,
                GtfsTrip.headsign,
                GtfsTrip.direction_id,
                candidates.c.departure_secs,
                arrival.arrival_secs,
                candidates.c.origin_sequence,
                candidates.c.destination_sequence,
            )
            .select_from(candidates)
            .join(GtfsTrip, GtfsTrip.id == candidates.c.trip_pk)
            .join(GtfsRoute, GtfsRoute.route_id == GtfsTrip.route_id)
            .join(
                arrival,
                and_(
                    arrival.trip_pk == candidates.c.trip_pk,
                    arrival.stop_sequence == candidates.c.destination_sequence,
                ),
            )
            .order_by(candidates.c.departure_secs, arrival.arrival_secs, GtfsTrip.trip_id)
            .limit(limit)
        ).all()
        return [ScheduledRide(*row) for row in rows]

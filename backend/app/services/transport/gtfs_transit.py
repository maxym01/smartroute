"""``TransitTimeProvider`` oparty o rozkład GTFS Static.

Zwraca czas z rozkładu (``DataSource.GTFS_SCHEDULE``), gdy podróż ma ``origin_stop_id``,
``destination_stop_id`` i ``departure_at`` oraz istnieje bezpośrednie połączenie w oknie czasu.
W każdym innym przypadku zwraca dotychczasowy szacunek parametryczny
(``DataSource.PARAMETRIC_ESTIMATE``) z wyjaśnieniem w założeniach. Podróże bez żadnego
z tych pól dostają szacunek bez zmian, dokładnie jak przed integracją GTFS.
"""

from sqlalchemy.exc import SQLAlchemyError

from app.core.enums import DataSource
from app.core.timezone import as_local_aware
from app.core.transport_params import PublicTransportParams
from app.services.gtfs.schedule_service import (
    ConnectionSearch,
    GtfsNotImportedError,
    ScheduleService,
    UnknownStopError,
)
from app.services.transport.base import DURATION_DECIMALS, TripInput, fmt_number
from app.services.transport.public_transport import (
    ParametricTransitTimeProvider,
    TransitTimeEstimate,
)


class GtfsTransitTimeProvider:
    def __init__(
        self,
        schedule: ScheduleService | None,
        params: PublicTransportParams,
        *,
        window_min: int,
    ) -> None:
        self.schedule = schedule
        self.fallback = ParametricTransitTimeProvider(params)
        self.window_min = window_min

    def estimate(self, trip: TripInput) -> TransitTimeEstimate:
        fields = (trip.origin_stop_id, trip.destination_stop_id, trip.departure_at)
        if not any(fields):
            return self.fallback.estimate(trip)
        if not all(fields):
            return self._fallback(
                trip,
                "Do użycia rozkładu GTFS potrzebne są origin_stop_id, destination_stop_id "
                "i departure_at.",
            )
        if self.schedule is None:
            return self._fallback(trip, "Rozkład GTFS nie został zaimportowany.")

        assert trip.origin_stop_id and trip.destination_stop_id and trip.departure_at
        departure = as_local_aware(trip.departure_at)
        try:
            search = self.schedule.find_direct_connections(
                trip.origin_stop_id,
                trip.destination_stop_id,
                departure,
                window_min=self.window_min,
                limit=1,
            )
        except GtfsNotImportedError:
            return self._fallback(trip, "Rozkład GTFS nie został zaimportowany.")
        except UnknownStopError as exc:
            return self._fallback(
                trip, f"Przystanek o id={exc.resource_id} nie istnieje w rozkładzie GTFS."
            )
        except SQLAlchemyError:
            return self._fallback(trip, "Nie udało się odczytać rozkładu GTFS.")

        if not search.connections:
            return self._fallback(
                trip,
                f"Brak bezpośredniego połączenia w rozkładzie GTFS w ciągu {self.window_min} min "
                f"od {search.departure_at:%d.%m.%Y %H:%M}.",
            )
        return self._from_schedule(search)

    def _fallback(self, trip: TripInput, reason: str) -> TransitTimeEstimate:
        estimate = self.fallback.estimate(trip)
        return TransitTimeEstimate(
            duration_min=estimate.duration_min,
            data_source=estimate.data_source,
            assumptions=(f"{reason} Użyto szacunku parametrycznego.", *estimate.assumptions),
        )

    @staticmethod
    def _from_schedule(search: ConnectionSearch) -> TransitTimeEstimate:
        connection = search.connections[0]
        wait_min = (connection.departure_at - search.departure_at).total_seconds() / 60
        total_min = (connection.arrival_at - search.departure_at).total_seconds() / 60
        direction = f" w kierunku {connection.headsign}" if connection.headsign else ""
        return TransitTimeEstimate(
            duration_min=total_min,
            data_source=DataSource.GTFS_SCHEDULE,
            assumptions=(
                f"Czas z rozkładu GTFS: linia {connection.line}{direction}, odjazd "
                f"{connection.departure_at:%d.%m.%Y %H:%M} z przystanku "
                f"{search.origin.stop_name}, przyjazd {connection.arrival_at:%H:%M} na przystanek "
                f"{search.destination.stop_name}.",
                f"Czas = oczekiwanie {fmt_number(wait_min, 0)} min od podanej godziny wyjazdu "
                f"+ przejazd {fmt_number(connection.duration_min, DURATION_DECIMALS)} min; "
                "bez dojścia do i z przystanku.",
                "Rozkład planowy (GTFS Static) — bez opóźnień i danych w czasie rzeczywistym; "
                "tylko połączenia bezpośrednie.",
            ),
        )

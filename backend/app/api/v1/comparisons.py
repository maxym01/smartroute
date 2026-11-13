from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.enums import TripPriority
from app.core.exceptions import NotFoundError
from app.db.gtfs_session import get_gtfs_db
from app.db.session import get_db
from app.repositories.gtfs_repository import GtfsRepository
from app.repositories.trip_repository import TripRepository
from app.schemas.comparison import ComparisonResponse
from app.services.comparison_service import ComparisonService
from app.services.gtfs.schedule_service import ScheduleService
from app.services.transport import TripInput
from app.services.transport.gtfs_transit import GtfsTransitTimeProvider
from app.services.weather import WeatherbitClient, WeatherService

router = APIRouter(tags=["comparisons"])


def get_weather_client(request: Request) -> WeatherbitClient | None:
    return getattr(request.app.state, "weather_client", None)


def get_comparison_service(
    settings: Annotated[Settings, Depends(get_settings)],
    gtfs_db: Annotated[Session | None, Depends(get_gtfs_db)],
    weather_client: Annotated[WeatherbitClient | None, Depends(get_weather_client)],
) -> ComparisonService:
    # The GTFS timetable is optional: without an import (gtfs_db=None) the provider returns
    # the parametric estimate, and trips without stops and a date always use that estimate.
    schedule = ScheduleService(GtfsRepository(gtfs_db)) if gtfs_db is not None else None
    provider = GtfsTransitTimeProvider(
        schedule,
        settings.transport.public_transport,
        window_min=settings.gtfs_search_window_min,
    )
    # Weather: location comes only from GTFS stop coordinates; any error = no adjustment.
    weather = WeatherService(
        weather_client,
        GtfsRepository(gtfs_db) if gtfs_db is not None else None,
        max_lead_min=settings.weather_max_lead_min,
    )
    return ComparisonService.from_settings(settings.transport, provider, weather)


@router.get(
    "/trips/{trip_id}/compare",
    response_model=ComparisonResponse,
    summary="Porównanie środków transportu i rekomendacja dla zapisanej podróży",
)
def compare_trip(
    trip_id: Annotated[int, Path(ge=1, description="Identyfikator podróży")],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ComparisonService, Depends(get_comparison_service)],
    priority: Annotated[
        TripPriority | None,
        Query(description="Opcjonalnie nadpisuje zapisany priorytet (bez zapisu w bazie)"),
    ] = None,
) -> ComparisonResponse:
    trip = TripRepository(db).get(trip_id)
    if trip is None:
        raise NotFoundError("Podróż", trip_id)

    result = service.compare(
        TripInput(
            distance_km=trip.distance_km,
            passengers=trip.passengers,
            has_car=trip.has_car,
            allow_bike=trip.allow_bike,
            origin=trip.origin,
            destination=trip.destination,
            origin_stop_id=trip.origin_stop_id,
            destination_stop_id=trip.destination_stop_id,
            departure_at=trip.departure_at,
        ),
        priority or trip.priority,
    )
    return ComparisonResponse.from_result(trip.id, result)

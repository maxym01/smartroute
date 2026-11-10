from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.enums import TripPriority
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.repositories.trip_repository import TripRepository
from app.schemas.comparison import ComparisonResponse
from app.services.comparison_service import ComparisonService
from app.services.transport import TripInput

router = APIRouter(tags=["comparisons"])


def get_comparison_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ComparisonService:
    # Punkt wpięcia dla GTFS: tu zostanie przekazany transit_time_provider.
    return ComparisonService.from_settings(settings.transport)


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
        ),
        priority or trip.priority,
    )
    return ComparisonResponse.from_result(trip.id, result)

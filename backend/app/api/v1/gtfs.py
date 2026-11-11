from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import GtfsNotImportedError
from app.core.timezone import LOCAL_TIMEZONE, as_local_aware
from app.db.gtfs_session import get_gtfs_db
from app.repositories.gtfs_repository import GtfsRepository
from app.schemas.gtfs import ConnectionList, StopList, StopRead
from app.services.gtfs.schedule_service import ScheduleService

router = APIRouter(tags=["gtfs"])

StopIdQuery = Annotated[str, Query(min_length=1, max_length=64, description="stop_id z /stops")]


def get_schedule_service(
    db: Annotated[Session | None, Depends(get_gtfs_db)],
) -> ScheduleService:
    if db is None:
        raise GtfsNotImportedError()
    return ScheduleService(GtfsRepository(db))


Schedule = Annotated[ScheduleService, Depends(get_schedule_service)]


@router.get("/stops", response_model=StopList, summary="Wyszukiwanie przystanków (GTFS)")
def search_stops(
    schedule: Schedule,
    query: Annotated[
        str,
        Query(
            min_length=2,
            max_length=100,
            description="Fragment nazwy (bez względu na wielkość liter i polskie znaki) "
            "albo dokładny stop_id / stop_code",
        ),
    ],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> StopList:
    schedule.require_feed()
    stops = schedule.repository.search_stops(query, limit)
    return StopList(items=[StopRead.model_validate(stop) for stop in stops], count=len(stops))


@router.get(
    "/connections",
    response_model=ConnectionList,
    summary="Bezpośrednie połączenia z rozkładu GTFS (bez przesiadek, bez realtime)",
)
def find_connections(
    schedule: Schedule,
    origin_stop_id: StopIdQuery,
    destination_stop_id: StopIdQuery,
    departure_at: Annotated[
        datetime | None,
        Query(
            description="Najwcześniejszy odjazd (ISO 8601). Bez strefy = Europe/Warsaw. "
            "Domyślnie: teraz."
        ),
    ] = None,
    window_min: Annotated[int, Query(ge=1, le=1440, description="Okno wyszukiwania [min]")] = 120,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> ConnectionList:
    if origin_stop_id == destination_stop_id:
        raise RequestValidationError(
            [
                {
                    "loc": ("query", "destination_stop_id"),
                    "msg": "Przystanek startowy i docelowy muszą się różnić",
                    "type": "value_error",
                }
            ]
        )
    start = as_local_aware(departure_at) if departure_at else datetime.now(LOCAL_TIMEZONE)
    search = schedule.find_direct_connections(
        origin_stop_id, destination_stop_id, start, window_min=window_min, limit=limit
    )
    return ConnectionList.from_search(search)

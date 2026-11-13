from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.trip import Trip
from app.repositories.trip_repository import TripRepository
from app.schemas.trip import TripCreate, TripList, TripRead, TripUpdate

router = APIRouter(prefix="/trips", tags=["trips"])

TripId = Annotated[int, Path(ge=1, description="Identyfikator podróży")]


def get_trip_repository(db: Annotated[Session, Depends(get_db)]) -> TripRepository:
    return TripRepository(db)


Repo = Annotated[TripRepository, Depends(get_trip_repository)]


def _get_or_404(repo: TripRepository, trip_id: int) -> Trip:
    trip = repo.get(trip_id)
    if trip is None:
        raise NotFoundError("Podróż", trip_id)
    return trip


@router.get("", response_model=TripList, summary="Lista podróży")
def list_trips(
    repo: Repo,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[
        str | None, Query(max_length=100, description="Szukaj w nazwie i miejscach")
    ] = None,
) -> TripList:
    query = q.strip() if q else None
    items, total = repo.list(skip=skip, limit=limit, q=query or None)
    return TripList(
        items=[TripRead.model_validate(trip) for trip in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "", response_model=TripRead, status_code=status.HTTP_201_CREATED, summary="Nowa podróż"
)
def create_trip(payload: TripCreate, repo: Repo) -> Trip:
    return repo.create(payload)


@router.get("/{trip_id}", response_model=TripRead, summary="Szczegóły podróży")
def get_trip(trip_id: TripId, repo: Repo) -> Trip:
    return _get_or_404(repo, trip_id)


@router.put("/{trip_id}", response_model=TripRead, summary="Pełna aktualizacja podróży")
def replace_trip(trip_id: TripId, payload: TripCreate, repo: Repo) -> Trip:
    trip = _get_or_404(repo, trip_id)
    return repo.update(trip, payload.model_dump())


@router.patch("/{trip_id}", response_model=TripRead, summary="Częściowa aktualizacja podróży")
def update_trip(trip_id: TripId, payload: TripUpdate, repo: Repo) -> Trip:
    trip = _get_or_404(repo, trip_id)
    changes = payload.model_dump(exclude_unset=True)

    # Cross-field rules (e.g. origin != destination) are checked on the merged state.
    current = TripCreate.model_validate(trip, from_attributes=True).model_dump()
    try:
        merged = TripCreate.model_validate({**current, **changes})
    except ValidationError as exc:
        raise RequestValidationError(
            [{**error, "loc": ("body", *error["loc"])} for error in exc.errors()]
        ) from exc

    return repo.update(trip, merged.model_dump(include=set(changes)))


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Usunięcie podróży")
def delete_trip(trip_id: TripId, repo: Repo) -> Response:
    repo.delete(_get_or_404(repo, trip_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

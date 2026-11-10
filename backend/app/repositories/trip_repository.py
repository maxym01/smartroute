from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.models.trip import Trip
from app.schemas.trip import TripCreate


class TripRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(
        self, *, skip: int = 0, limit: int = 20, q: str | None = None
    ) -> tuple[Sequence[Trip], int]:
        filters: list[ColumnElement[bool]] = []
        if q:
            needle = q.casefold()
            filters.append(
                or_(
                    *(
                        func.lower(column).contains(needle, autoescape=True)
                        for column in (Trip.name, Trip.origin, Trip.destination)
                    )
                )
            )

        total = self.session.scalar(select(func.count()).select_from(Trip).where(*filters)) or 0
        items = self.session.scalars(
            select(Trip)
            .where(*filters)
            .order_by(Trip.created_at.desc(), Trip.id.desc())
            .offset(skip)
            .limit(limit)
        ).all()
        return items, total

    def get(self, trip_id: int) -> Trip | None:
        return self.session.get(Trip, trip_id)

    def create(self, data: TripCreate) -> Trip:
        trip = Trip(**data.model_dump())
        self.session.add(trip)
        self._commit_and_refresh(trip)
        return trip

    def update(self, trip: Trip, changes: Mapping[str, Any]) -> Trip:
        for field, value in changes.items():
            setattr(trip, field, value)
        self._commit_and_refresh(trip)
        return trip

    def delete(self, trip: Trip) -> None:
        self.session.delete(trip)
        self.session.commit()

    def _commit_and_refresh(self, trip: Trip) -> None:
        # refresh ładuje wartości wyliczone po stronie bazy (created_at/updated_at).
        self.session.commit()
        self.session.refresh(trip)

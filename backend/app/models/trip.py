from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TripPriority(StrEnum):
    FASTEST = "fastest"
    CHEAPEST = "cheapest"
    GREENEST = "greenest"
    BALANCED = "balanced"


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    origin: Mapped[str] = mapped_column(String(200))
    destination: Mapped[str] = mapped_column(String(200))
    distance_km: Mapped[float] = mapped_column(Float)
    passengers: Mapped[int] = mapped_column(Integer, default=1)
    priority: Mapped[TripPriority] = mapped_column(
        Enum(
            TripPriority,
            name="trip_priority",
            native_enum=False,
            length=20,
            validate_strings=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=TripPriority.BALANCED,
    )
    has_car: Mapped[bool] = mapped_column(default=True)
    allow_bike: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[str | None] = mapped_column(String(500), default=None)
    # SQLite CURRENT_TIMESTAMP zwraca czas UTC (bez strefy) — strefę dokłada schemat TripRead.
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"Trip(id={self.id!r}, name={self.name!r})"

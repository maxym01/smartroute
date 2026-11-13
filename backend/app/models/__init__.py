"""ORM model registry: importing it guarantees the tables are registered in ``Base.metadata``."""

from app.models.trip import Trip, TripPriority

__all__ = ["Trip", "TripPriority"]

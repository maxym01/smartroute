"""Rejestr modeli ORM — import gwarantuje, że tabele trafią do ``Base.metadata``."""

from app.models.trip import Trip, TripPriority

__all__ = ["Trip", "TripPriority"]

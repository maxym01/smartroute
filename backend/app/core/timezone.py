"""Strefa czasowa aplikacji.

Daty bez strefy (np. ``2026-11-12T08:00``) podane przez klienta interpretujemy jako czas lokalny
Gdańska. Wymaga pakietu ``tzdata`` na Windows (brak systemowej bazy stref).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

LOCAL_TIMEZONE_NAME = "Europe/Warsaw"
LOCAL_TIMEZONE = ZoneInfo(LOCAL_TIMEZONE_NAME)


def as_local_aware(value: datetime) -> datetime:
    """Dodaje strefę Europe/Warsaw do daty naiwnej. Datę ze strefą zwraca bez zmian."""
    return value.replace(tzinfo=LOCAL_TIMEZONE) if value.tzinfo is None else value

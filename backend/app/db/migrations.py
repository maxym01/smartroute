"""Minimalne, idempotentne migracje schematu (Alembic jest poza zakresem MVP).

``create_all`` tworzy brakujące tabele, ale nie dodaje kolumn do istniejących. Tu dodajemy
nowe kolumny *nullable* przez ``ALTER TABLE ... ADD COLUMN`` — w SQLite to operacja
natychmiastowa, nie przepisuje tabeli i nie zmienia istniejących wierszy.
"""

import logging

from sqlalchemy import Engine, inspect

logger = logging.getLogger(__name__)

# tabela → [(kolumna, definicja SQL)] — tylko kolumny nullable bez wartości domyślnej.
ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "trips": [
        ("origin_stop_id", "VARCHAR(64)"),
        ("destination_stop_id", "VARCHAR(64)"),
        ("departure_at", "DATETIME"),
    ],
}


def upgrade_schema(engine: Engine) -> list[str]:
    """Dodaje brakujące kolumny. Zwraca listę dodanych (``tabela.kolumna``)."""
    added: list[str] = []
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        for table, columns in ADDED_COLUMNS.items():
            if table not in tables:
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {ddl}')
                    added.append(f"{table}.{name}")
    for column in added:
        logger.info("Migracja schematu: dodano kolumnę %s", column)
    return added

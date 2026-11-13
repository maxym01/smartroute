"""Minimal, idempotent schema migrations (Alembic is out of the MVP scope).

``create_all`` creates missing tables but does not add columns to existing ones. Here new
*nullable* columns are added with ``ALTER TABLE ... ADD COLUMN``. In SQLite this is an
instant operation that does not rewrite the table or change existing rows.
"""

import logging

from sqlalchemy import Engine, inspect

logger = logging.getLogger(__name__)

# table → [(column, SQL definition)] — only nullable columns without a default value.
ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "trips": [
        ("origin_stop_id", "VARCHAR(64)"),
        ("destination_stop_id", "VARCHAR(64)"),
        ("departure_at", "DATETIME"),
    ],
}


def upgrade_schema(engine: Engine) -> list[str]:
    """Add missing columns. Return the list of added ones (``table.column``)."""
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

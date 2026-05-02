"""Lightweight SQLite schema bootstrap and migration tracking."""

from datetime import datetime

from sqlalchemy import Column, DateTime, MetaData, String, Table, insert, select, text
from sqlalchemy.engine import Engine

from comp_synth.store.models import Base

CURRENT_SCHEMA_MIGRATION_ID = "0001_create_current_schema"
TAGS_COLUMN_MIGRATION_ID = "0002_add_tags_column"

_metadata = MetaData()

schema_migrations = Table(
    "schema_migrations",
    _metadata,
    Column("migration_id", String, primary_key=True),
    Column("applied_at", DateTime, nullable=False),
)


def _migration_applied(conn, migration_id: str) -> bool:
    return (
        conn.execute(
            select(schema_migrations.c.migration_id).where(
                schema_migrations.c.migration_id == migration_id
            )
        ).scalar_one_or_none()
        is not None
    )


def _run_0002_add_tags_column(conn) -> None:
    if _migration_applied(conn, TAGS_COLUMN_MIGRATION_ID):
        return
    cols = {row[1] for row in conn.execute(text("PRAGMA table_info(articles)"))}
    if "tags" not in cols:
        conn.execute(text("ALTER TABLE articles ADD COLUMN tags TEXT"))
    conn.execute(
        text(
            "UPDATE articles SET tags = COALESCE(json_extract(extra_metadata, '$.tags'), '[]') "
            "WHERE tags IS NULL"
        )
    )
    conn.execute(
        insert(schema_migrations).values(
            migration_id=TAGS_COLUMN_MIGRATION_ID,
            applied_at=datetime.now(),
        )
    )


def bootstrap_database(engine: Engine) -> None:
    """Create current tables and record the baseline schema migration."""
    Base.metadata.create_all(engine)
    _metadata.create_all(engine)
    with engine.begin() as conn:
        if not _migration_applied(conn, CURRENT_SCHEMA_MIGRATION_ID):
            conn.execute(
                insert(schema_migrations).values(
                    migration_id=CURRENT_SCHEMA_MIGRATION_ID,
                    applied_at=datetime.now(),
                )
            )
        _run_0002_add_tags_column(conn)

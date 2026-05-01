"""Lightweight SQLite schema bootstrap and migration tracking."""

from datetime import datetime

from sqlalchemy import Column, DateTime, MetaData, String, Table, insert, select
from sqlalchemy.engine import Engine

from comp_synth.store.models import Base

CURRENT_SCHEMA_MIGRATION_ID = "0001_create_current_schema"

_metadata = MetaData()

schema_migrations = Table(
    "schema_migrations",
    _metadata,
    Column("migration_id", String, primary_key=True),
    Column("applied_at", DateTime, nullable=False),
)


def bootstrap_database(engine: Engine) -> None:
    """Create current tables and record the baseline schema migration."""
    Base.metadata.create_all(engine)
    _metadata.create_all(engine)
    with engine.begin() as conn:
        existing = conn.execute(
            select(schema_migrations.c.migration_id).where(
                schema_migrations.c.migration_id == CURRENT_SCHEMA_MIGRATION_ID
            )
        ).scalar_one_or_none()
        if existing is None:
            conn.execute(
                insert(schema_migrations).values(
                    migration_id=CURRENT_SCHEMA_MIGRATION_ID,
                    applied_at=datetime.now(),
                )
            )

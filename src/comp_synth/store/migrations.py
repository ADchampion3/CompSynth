"""Lightweight SQLite schema bootstrap and migration tracking."""

from datetime import datetime

from sqlalchemy import Column, DateTime, MetaData, String, Table, insert, select, text
from sqlalchemy.engine import Engine

from comp_synth.store.models import Base

CURRENT_SCHEMA_MIGRATION_ID = "0001_create_current_schema"
TAGS_COLUMN_MIGRATION_ID = "0002_add_tags_column"
BACKFILL_MIGRATION_ID = "0003_backfill_source_key_and_tags"
SETTINGS_TABLE_MIGRATION_ID = "0004_create_settings_table"
SOURCE_KEY_COLUMN_MIGRATION_ID = "0005_add_source_key_column"

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


def _run_0003_backfill_source_key_and_tags(conn) -> None:
    if _migration_applied(conn, BACKFILL_MIGRATION_ID):
        return
    # Backfill tags from extra_metadata.tags where tags column is empty
    conn.execute(text(
        "UPDATE articles SET tags = json_extract(extra_metadata, '$.tags') "
        "WHERE (tags IS NULL OR tags = '[]' OR tags LIKE '%其他%') "
        "AND json_extract(extra_metadata, '$.tags') IS NOT NULL "
        "AND json_array_length(json_extract(extra_metadata, '$.tags')) > 0"
    ))
    # Backfill source_key from sources table by matching URL prefix.
    # Use SUBSTR comparison instead of LIKE to avoid wildcard interpretation
    # of '_' and '%' in source URLs.
    conn.execute(text(
        "UPDATE articles SET extra_metadata = json_set(extra_metadata, '$.source_key', "
        "  (SELECT s.source_key FROM sources s "
        "   WHERE SUBSTR(articles.url, 1, LENGTH(s.url)) = s.url "
        "   LIMIT 1)) "
        "WHERE json_extract(extra_metadata, '$.source_key') IS NULL "
        "AND EXISTS (SELECT 1 FROM sources s "
        "   WHERE SUBSTR(articles.url, 1, LENGTH(s.url)) = s.url)"
    ))
    conn.execute(
        insert(schema_migrations).values(
            migration_id=BACKFILL_MIGRATION_ID,
            applied_at=datetime.now(),
        )
    )


def _run_0004_create_settings_table(conn) -> None:
    if _migration_applied(conn, SETTINGS_TABLE_MIGRATION_ID):
        return
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS settings ("
        "  id INTEGER PRIMARY KEY CHECK (id = 1),"
        "  data TEXT NOT NULL DEFAULT '{}',"
        "  updated_at TEXT NOT NULL DEFAULT (datetime('now'))"
        ")"
    ))
    conn.execute(
        insert(schema_migrations).values(
            migration_id=SETTINGS_TABLE_MIGRATION_ID,
            applied_at=datetime.now(),
        )
    )


def _run_0005_add_source_key_column(conn) -> None:
    if _migration_applied(conn, SOURCE_KEY_COLUMN_MIGRATION_ID):
        return
    cols = {row[1] for row in conn.execute(text("PRAGMA table_info(articles)"))}
    if "source_key" not in cols:
        conn.execute(text("ALTER TABLE articles ADD COLUMN source_key TEXT NOT NULL DEFAULT ''"))
    # Backfill source_key from extra_metadata if not already set
    conn.execute(text(
        "UPDATE articles SET source_key = COALESCE("
        "  json_extract(extra_metadata, '$.source_key'),"
        "  source"
        ") WHERE source_key = ''"
    ))
    conn.execute(
        insert(schema_migrations).values(
            migration_id=SOURCE_KEY_COLUMN_MIGRATION_ID,
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
        _run_0003_backfill_source_key_and_tags(conn)
        _run_0004_create_settings_table(conn)
        _run_0005_add_source_key_column(conn)

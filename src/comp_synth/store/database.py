"""Shared database engine factory with WAL mode for SQLite."""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from comp_synth.store.migrations import bootstrap_database
from comp_synth.store.models import resolve_db_path

_engines: dict[str, tuple] = {}


def get_engine(db_path: Path | None = None, default_filename: str = "crawl_state.db") -> tuple:
    """Return a shared (engine, session_factory) for the given database path.

    Caches by resolved absolute path so all callers share one connection pool.
    Enables WAL mode, NORMAL synchronous, and a 5-second busy timeout.
    """
    resolved = resolve_db_path(db_path, default_filename)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    key = str(resolved)

    if key in _engines:
        return _engines[key]

    engine = create_engine(f"sqlite:///{resolved}", echo=False)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    bootstrap_database(engine)
    session_factory = sessionmaker(bind=engine)
    _engines[key] = (engine, session_factory)
    return _engines[key]


def reset_engines() -> None:
    """Clear cached engines (for testing)."""
    for engine, _ in _engines.values():
        engine.dispose()
    _engines.clear()

from sqlalchemy import create_engine, inspect, text

from comp_synth.store.migrations import bootstrap_database


def test_bootstrap_database_creates_tables_and_migration_record(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'crawl_state.db'}")

    bootstrap_database(engine)

    inspector = inspect(engine)
    assert "schema_migrations" in inspector.get_table_names()
    assert "sources" in inspector.get_table_names()
    assert "crawl_runs" in inspector.get_table_names()
    assert "reports" in inspector.get_table_names()

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT migration_id FROM schema_migrations")).fetchall()

    assert rows == [("0001_create_current_schema",)]


def test_bootstrap_database_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'crawl_state.db'}")

    bootstrap_database(engine)
    bootstrap_database(engine)

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM schema_migrations WHERE migration_id = '0001_create_current_schema'")
        ).scalar_one()

    assert count == 1

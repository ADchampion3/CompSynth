import json

from sqlalchemy import create_engine, inspect, text

from comp_synth.store.migrations import bootstrap_database


def _create_pre_migration_db(path):
    """Create a database simulating state before tags migration (0001 only)."""
    engine = create_engine(f"sqlite:///{path}")
    # Create articles table WITHOUT tags column (simulating pre-0002 state)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE articles (
                article_id VARCHAR NOT NULL,
                vector_id VARCHAR NOT NULL,
                crawled_at DATETIME NOT NULL,
                published_at DATETIME,
                content TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                url VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                extra_metadata JSON,
                liked INTEGER DEFAULT 0
            )
        """))
        conn.execute(text("""
            CREATE TABLE schema_migrations (
                migration_id VARCHAR PRIMARY KEY,
                applied_at DATETIME NOT NULL
            )
        """))
    return engine


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

    ids = [r[0] for r in rows]
    assert "0001_create_current_schema" in ids
    assert "0002_add_tags_column" in ids


def test_bootstrap_database_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'crawl_state.db'}")

    bootstrap_database(engine)
    bootstrap_database(engine)

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM schema_migrations WHERE migration_id = '0001_create_current_schema'")
        ).scalar_one()

    assert count == 1


# --- Tags column migration ---


def test_tags_column_exists_after_bootstrap(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'crawl_state.db'}")
    bootstrap_database(engine)
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("articles")}
    assert "tags" in cols


def test_migration_backfills_tags_from_extra_metadata(tmp_path):
    engine = _create_pre_migration_db(tmp_path / "crawl_state.db")

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO schema_migrations (migration_id, applied_at) VALUES ('0001_create_current_schema', '2026-01-01')"
        ))
        conn.execute(text(
            "INSERT INTO articles (article_id, vector_id, crawled_at, url, source, extra_metadata, liked) "
            "VALUES ('a:1', 'a:1', '2026-01-01', 'https://x.com/1', 'a', "
            "'{\"tags\": [\"技术博客\", \"比赛信息\"]}', 0)"
        ))
        conn.execute(text(
            "INSERT INTO articles (article_id, vector_id, crawled_at, url, source, extra_metadata, liked) "
            "VALUES ('a:2', 'a:2', '2026-01-01', 'https://x.com/2', 'a', '{}', 0)"
        ))

    bootstrap_database(engine)

    with engine.connect() as conn:
        r1 = conn.execute(text("SELECT tags FROM articles WHERE article_id = 'a:1'")).scalar_one()
        r2 = conn.execute(text("SELECT tags FROM articles WHERE article_id = 'a:2'")).scalar_one()
    assert json.loads(r1) == ["技术博客", "比赛信息"]
    assert json.loads(r2) == []


def test_migration_idempotent_does_not_overwrite_cleared_tags(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'crawl_state.db'}")
    bootstrap_database(engine)

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO articles (article_id, vector_id, crawled_at, url, source, content, summary, title, extra_metadata, tags, liked) "
            "VALUES ('a:1', 'a:1', '2026-01-01', 'https://x.com/1', 'a', '', '', '', '{\"tags\":[\"old\"]}', '[]', 0)"
        ))

    # Run bootstrap again -- should NOT overwrite tags='[]'
    bootstrap_database(engine)

    with engine.connect() as conn:
        tags = conn.execute(text("SELECT tags FROM articles WHERE article_id = 'a:1'")).scalar_one()
    assert json.loads(tags) == []


def test_migration_handles_null_extra_metadata(tmp_path):
    engine = _create_pre_migration_db(tmp_path / "crawl_state.db")

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO schema_migrations (migration_id, applied_at) VALUES ('0001_create_current_schema', '2026-01-01')"
        ))
        conn.execute(text(
            "INSERT INTO articles (article_id, vector_id, crawled_at, url, source, extra_metadata, liked) "
            "VALUES ('a:1', 'a:1', '2026-01-01', 'https://x.com/1', 'a', NULL, 0)"
        ))

    bootstrap_database(engine)

    with engine.connect() as conn:
        tags = conn.execute(text("SELECT tags FROM articles WHERE article_id = 'a:1'")).scalar_one()
    assert json.loads(tags) == []

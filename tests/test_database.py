"""Tests for the shared database engine factory (Phase 1.1)."""

from pathlib import Path

import pytest
from sqlalchemy import text

from comp_synth.store.database import get_engine, reset_engines


@pytest.fixture(autouse=True)
def _clean_engine_cache():
    reset_engines()
    yield
    reset_engines()


class TestGetEngine:
    def test_returns_shared_instance_for_same_path(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        engine_a, factory_a = get_engine(db_path, "test.db")
        engine_b, factory_b = get_engine(db_path, "test.db")
        assert engine_a is engine_b
        assert factory_a is factory_b

    def test_returns_different_engines_for_different_paths(self, tmp_path: Path):
        path_a = tmp_path / "a.db"
        path_b = tmp_path / "b.db"
        engine_a, _ = get_engine(path_a, "a.db")
        engine_b, _ = get_engine(path_b, "b.db")
        assert engine_a is not engine_b

    def test_creates_parent_directory(self, tmp_path: Path):
        db_path = tmp_path / "nested" / "dir" / "test.db"
        get_engine(db_path, "test.db")
        assert db_path.parent.exists()

    def test_engine_is_functional(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        engine, factory = get_engine(db_path, "test.db")
        with factory() as session:
            result = session.execute(text("SELECT 1"))
            assert result.scalar() == 1


class TestWalPragma:
    def test_journal_mode_is_wal(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        engine, _ = get_engine(db_path, "test.db")
        with engine.connect() as conn:
            mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            assert mode == "wal"

    def test_synchronous_is_normal(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        engine, _ = get_engine(db_path, "test.db")
        with engine.connect() as conn:
            sync = conn.execute(text("PRAGMA synchronous")).scalar()
            assert sync == 1  # NORMAL = 1

    def test_busy_timeout_is_set(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        engine, _ = get_engine(db_path, "test.db")
        with engine.connect() as conn:
            timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()
            assert timeout == 5000


class TestResetEngines:
    def test_clears_cache(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        get_engine(db_path, "test.db")
        reset_engines()
        from comp_synth.store import database
        assert len(database._engines) == 0

    def test_new_engine_after_reset(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        engine_before, _ = get_engine(db_path, "test.db")
        reset_engines()
        engine_after, _ = get_engine(db_path, "test.db")
        assert engine_before is not engine_after

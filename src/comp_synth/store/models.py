"""SQLAlchemy ORM models for the store layer."""

from datetime import datetime
from pathlib import Path

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def resolve_db_path(path: Path, default_filename: str) -> Path:
    """Resolve a path that may be a directory or a file.

    - If path is a directory: return path / default_filename
    - If path is a file: return path as-is
    - If path has no extension (bare name): treat as directory
    """
    if path.is_dir() or not path.suffix:
        return path / default_filename
    return path


class Base(DeclarativeBase):
    pass


class ArticleModel(Base):
    """Article metadata stored in SQLite."""

    __tablename__ = "articles"

    article_id: Mapped[str] = mapped_column(String, primary_key=True)
    vector_id: Mapped[str] = mapped_column(String, nullable=False)
    crawled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    liked: Mapped[int] = mapped_column(Integer, default=0)


class SiteSchemaModel(Base):
    """Site CSS selector schema cached in SQLite."""

    __tablename__ = "site_schemas"

    site_name: Mapped[str] = mapped_column(String, primary_key=True)
    site_url: Mapped[str] = mapped_column(String, nullable=False)
    selectors: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_llm_call: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_stale_refresh_call: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stale_refresh_count: Mapped[int] = mapped_column(Integer, default=0)
    list_selectors: Mapped[dict] = mapped_column(JSON, default=dict)


class SourceCrawlOutcomeModel(Base):
    """Per-source crawl outcome used for selector health decisions."""

    __tablename__ = "source_crawl_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    site_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    new_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    crawled_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)

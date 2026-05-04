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
    source_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    crawled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    tags: Mapped[str] = mapped_column(Text, default="[]")
    liked: Mapped[int] = mapped_column(Integer, default=0)


class ArticleStateModel(Base):
    """User-controlled reading state for an article."""

    __tablename__ = "article_states"

    article_id: Mapped[str] = mapped_column(String, primary_key=True)
    read_state: Mapped[str] = mapped_column(String, nullable=False, default="unread")
    user_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


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


class SourceModel(Base):
    """Managed subscription source configuration."""

    __tablename__ = "sources"

    source_key: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    selectors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    javascript: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    crawl_frequency: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    priority: Mapped[str] = mapped_column(String, nullable=False, default="normal")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_config: Mapped[dict] = mapped_column(JSON, default=dict)


class CrawlRunModel(Base):
    """Top-level crawl run status and summary."""

    __tablename__ = "crawl_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    new_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class CrawlRunSourceModel(Base):
    """Per-source progress and outcome for a crawl run."""

    __tablename__ = "crawl_run_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source_key: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    new_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReportModel(Base):
    """Generated report metadata while Markdown remains on disk."""

    __tablename__ = "reports"

    report_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    date_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    date_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    markdown_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)


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

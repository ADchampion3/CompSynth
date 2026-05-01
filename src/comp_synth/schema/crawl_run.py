"""Crawl run domain schema."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class CrawlRun:
    run_id: str
    scope: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    heartbeat_at: datetime | None = None
    new_items: int = 0
    errors: list[str] = field(default_factory=list)
    error_text: str | None = None


@dataclass(frozen=True)
class CrawlRunSource:
    id: int | None
    run_id: str
    source_key: str
    source_type: str
    source_url: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    new_items: int = 0
    error_text: str | None = None

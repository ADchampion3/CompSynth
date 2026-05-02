"""Pydantic request/response schemas for the CompSynth API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# --- Enums as Literal types ---

ReadState = Literal["unread", "read", "later", "ignored"]
CrawlRunStatus = Literal["running", "success", "partial", "failed", "timed_out"]
CrawlRunScope = Literal["all", "single"]
SourceRunStatus = Literal["running", "success", "failed"]
SourceType = Literal["rss", "web", "javascript"]
SourceHealthStatus = Literal["failed", "stale", "healthy"]


# --- Error envelope ---

class ErrorDetail(BaseModel):
    problem: str
    cause: str = ""
    fix: str = ""


# --- Article schemas ---


class ArticleResponse(BaseModel):
    article_id: str
    source: str
    url: str
    title: str = ""
    summary: str = ""
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    collected_at: datetime | None = None
    liked: int = 0
    read_state: ReadState | None = None


class ArticleStateResponse(BaseModel):
    article_id: str
    read_state: str
    user_note: str = ""
    last_viewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ArticlePageResponse(BaseModel):
    items: list[ArticleResponse]
    total: int
    limit: int
    offset: int


class ImportantArticleResponse(BaseModel):
    article: ArticleResponse
    importance_score: float


# --- Article request schemas ---


class ArticleStateUpdate(BaseModel):
    read_state: ReadState


class ArticleLikeUpdate(BaseModel):
    liked: bool


class ArticleNoteUpdate(BaseModel):
    user_note: str


class TagsUpdateRequest(BaseModel):
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        seen = set()
        result = []
        for tag in v:
            stripped = tag.strip()
            if not stripped:
                continue
            if len(stripped) > 50:
                raise ValueError(f"Tag too long (max 50 chars): {stripped[:20]}...")
            if any(ord(c) < 0x20 for c in stripped):
                raise ValueError(f"Tag contains control characters: {stripped[:20]}...")
            if stripped not in seen:
                seen.add(stripped)
                result.append(stripped)
        return result


class TagVocabularyResponse(BaseModel):
    tags: list[str]


# --- Source request schemas ---


class SourceCreateRequest(BaseModel):
    source_type: SourceType = "web"
    url: str = Field(..., min_length=1)
    name: str | None = None
    enabled: bool = True
    javascript: bool = False


class SourceUpdateRequest(BaseModel):
    url: str | None = None
    name: str | None = None
    source_type: SourceType | None = None
    enabled: bool | None = None
    javascript: bool | None = None


# --- Source schemas ---


class SelectorField(BaseModel):
    name: str = ""
    selector: str = ""
    type: str = ""


class SourceResponse(BaseModel):
    source_key: str
    source_type: str
    url: str
    name: str | None = None
    enabled: bool = True
    selectors: list[dict[str, str]] | None = None
    javascript: bool = False


# --- Crawl schemas ---


class CrawlRunResponse(BaseModel):
    run_id: str
    scope: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    new_items: int = 0
    errors: list[str] = Field(default_factory=list)
    error_text: str | None = None


class CrawlRunSourceResponse(BaseModel):
    id: int | None = None
    run_id: str
    source_key: str
    source_type: str
    source_url: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    new_items: int = 0
    error_text: str | None = None


class CrawlRunDetailResponse(BaseModel):
    run: CrawlRunResponse
    sources: list[CrawlRunSourceResponse] = Field(default_factory=list)


# --- Report schemas ---


class ReportSummaryResponse(BaseModel):
    report_id: str
    title: str
    created_at: datetime


class ReportDetailResponse(ReportSummaryResponse):
    markdown: str


# --- Source health schemas ---


class SourceHealthResponse(BaseModel):
    source_key: str
    source_type: str
    site_name: str
    source_url: str
    status: str
    last_crawled_at: datetime
    last_new_item_count: int
    recent_zero_days: int
    last_error: str | None = None


# --- Dashboard schemas ---


class DashboardSummaryResponse(BaseModel):
    article_count: int
    important_unread_count: int
    important_unread: list[ImportantArticleResponse]
    latest_crawl_run: CrawlRunResponse | None = None
    failed_sources: list[CrawlRunSourceResponse]
    unhealthy_sources: list[SourceHealthResponse]
    stale_running_runs: list[CrawlRunResponse]

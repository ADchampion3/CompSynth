"""Shared domain-object to API-response mappers."""

from comp_synth.api.schemas import (
    ArticleResponse,
    CrawlRunResponse,
    CrawlRunSourceResponse,
)


def content_item_to_response(item, read_state: str | None = None) -> ArticleResponse:
    return ArticleResponse(
        article_id=item.id,
        source=item.source,
        url=item.url,
        title=item.title,
        summary=item.summary,
        content=item.content,
        tags=item.tags,
        published_at=item.published_at,
        collected_at=item.collected_at,
        liked=item.metadata.get("_liked", 0) if isinstance(item.metadata, dict) else 0,
        read_state=read_state,
    )


def crawl_run_to_response(run) -> CrawlRunResponse:
    return CrawlRunResponse(
        run_id=run.run_id,
        scope=run.scope,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        new_items=run.new_items,
        errors=run.errors,
        error_text=run.error_text,
    )


def crawl_run_source_to_response(sr) -> CrawlRunSourceResponse:
    return CrawlRunSourceResponse(
        id=sr.id,
        run_id=sr.run_id,
        source_key=sr.source_key,
        source_type=sr.source_type,
        source_url=sr.source_url,
        status=sr.status,
        started_at=sr.started_at,
        finished_at=sr.finished_at,
        new_items=sr.new_items,
        error_text=sr.error_text,
    )

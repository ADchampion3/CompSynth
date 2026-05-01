"""Dashboard API router."""

from fastapi import APIRouter, Depends

from comp_synth.api.deps import get_dashboard_service
from comp_synth.api.mappers import (
    content_item_to_response,
    crawl_run_source_to_response,
    crawl_run_to_response,
)
from comp_synth.api.schemas import (
    DashboardSummaryResponse,
    ImportantArticleResponse,
    SourceHealthResponse,
)
from comp_synth.services.dashboard_service import DashboardService

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardSummaryResponse)
def get_dashboard(
    service: DashboardService = Depends(get_dashboard_service),
):
    summary = service.get_summary()

    important_unread = [
        ImportantArticleResponse(
            article=content_item_to_response(entry.article),
            importance_score=entry.importance_score,
        )
        for entry in summary.important_unread
    ]

    failed_sources = [crawl_run_source_to_response(sr) for sr in summary.failed_sources]

    unhealthy_sources = [
        SourceHealthResponse(
            source_key=s.source_key,
            source_type=s.source_type,
            site_name=s.site_name,
            source_url=s.source_url,
            status=s.status,
            last_crawled_at=s.last_crawled_at,
            last_new_item_count=s.last_new_item_count,
            recent_zero_days=s.recent_zero_days,
            last_error=s.last_error,
        )
        for s in summary.unhealthy_sources
    ]

    stale_runs = [crawl_run_to_response(r) for r in summary.stale_running_runs]

    return DashboardSummaryResponse(
        article_count=summary.article_count,
        important_unread_count=summary.important_unread_count,
        important_unread=important_unread,
        latest_crawl_run=crawl_run_to_response(summary.latest_crawl_run) if summary.latest_crawl_run else None,
        failed_sources=failed_sources,
        unhealthy_sources=unhealthy_sources,
        stale_running_runs=stale_runs,
    )

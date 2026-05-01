"""Dashboard aggregation service."""

from dataclasses import dataclass, field
from datetime import datetime

from comp_synth.schema.crawl_run import CrawlRun, CrawlRunSource
from comp_synth.services.article_service import ArticleService, ImportantArticle
from comp_synth.store.repositories.crawl_run_repository import CrawlRunRepository
from comp_synth.store.repositories.source_crawl_outcome_repository import (
    SourceCrawlOutcomeRepository,
    SourceHealth,
)


@dataclass(frozen=True)
class DashboardSummary:
    """API-friendly dashboard snapshot."""

    article_count: int
    important_unread_count: int
    important_unread: list[ImportantArticle] = field(default_factory=list)
    latest_crawl_run: CrawlRun | None = None
    failed_sources: list[CrawlRunSource] = field(default_factory=list)
    unhealthy_sources: list[SourceHealth] = field(default_factory=list)
    stale_running_runs: list[CrawlRun] = field(default_factory=list)


class DashboardService:
    """Aggregates service/repository data for an operational dashboard."""

    def __init__(
        self,
        article_service: ArticleService,
        crawl_run_repository: CrawlRunRepository | None = None,
        source_outcome_repository: SourceCrawlOutcomeRepository | None = None,
    ) -> None:
        self._article_service = article_service
        self._crawl_run_repository = crawl_run_repository
        self._source_outcome_repository = source_outcome_repository

    def get_summary(
        self,
        important_limit: int = 10,
        failed_source_limit: int = 10,
        source_health_lookback_days: int = 7,
        source_zero_day_threshold: int = 3,
        stale_run_after_minutes: int = 60,
        now: datetime | None = None,
    ) -> DashboardSummary:
        article_count = self._article_service.list_articles(limit=1).total
        important_unread = self._article_service.list_important_unread(limit=important_limit)
        latest_run = self._latest_crawl_run()
        failed_sources = self._failed_sources(latest_run, failed_source_limit)
        unhealthy_sources = self._unhealthy_sources(
            lookback_days=source_health_lookback_days,
            zero_day_threshold=source_zero_day_threshold,
        )
        stale_running_runs = self._stale_running_runs(stale_run_after_minutes, now)
        return DashboardSummary(
            article_count=article_count,
            important_unread_count=len(important_unread),
            important_unread=important_unread,
            latest_crawl_run=latest_run,
            failed_sources=failed_sources,
            unhealthy_sources=unhealthy_sources,
            stale_running_runs=stale_running_runs,
        )

    def _latest_crawl_run(self) -> CrawlRun | None:
        if self._crawl_run_repository is None:
            return None
        runs = self._crawl_run_repository.list_recent(limit=1)
        return runs[0] if runs else None

    def _failed_sources(self, latest_run: CrawlRun | None, limit: int) -> list[CrawlRunSource]:
        if self._crawl_run_repository is None or latest_run is None:
            return []
        safe_limit = max(1, min(limit, 100))
        return [
            source
            for source in self._crawl_run_repository.list_sources(latest_run.run_id)
            if source.status == "failed"
        ][:safe_limit]

    def _unhealthy_sources(self, lookback_days: int, zero_day_threshold: int) -> list[SourceHealth]:
        if self._source_outcome_repository is None:
            return []
        return [
            source
            for source in self._source_outcome_repository.list_source_health(
                lookback_days=lookback_days,
                zero_day_threshold=zero_day_threshold,
            )
            if source.status in {"failed", "stale"}
        ]

    def _stale_running_runs(self, stale_after_minutes: int, now: datetime | None) -> list[CrawlRun]:
        if self._crawl_run_repository is None:
            return []
        return self._crawl_run_repository.list_stale_running(
            stale_after_minutes=stale_after_minutes,
            now=now,
        )

"""Repository for per-source crawl outcomes."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comp_synth.store.models import SourceCrawlOutcomeModel


class SourceCrawlOutcomeRepository:
    """Data access for source crawl outcomes."""

    def __init__(self, session: Session):
        self._session = session

    def record(
        self,
        source_key: str,
        source_type: str,
        site_name: str,
        source_url: str,
        new_item_count: int,
        error: str | None,
        crawled_at: datetime | None = None,
    ) -> None:
        """Record one source crawl outcome."""
        self._session.add(
            SourceCrawlOutcomeModel(
                source_key=source_key,
                source_type=source_type,
                site_name=site_name,
                source_url=source_url,
                new_item_count=new_item_count,
                error=error,
                crawled_at=crawled_at or datetime.now(),
            )
        )

    def count_recent_zero_days(
        self,
        source_key: str,
        lookback_days: int,
        now: datetime | None = None,
    ) -> int:
        """Count distinct recent crawl dates with zero new items and no error."""
        now = now or datetime.now()
        cutoff = now - timedelta(days=lookback_days)
        stmt = select(func.count(func.distinct(func.date(SourceCrawlOutcomeModel.crawled_at)))).where(
            SourceCrawlOutcomeModel.source_key == source_key,
            SourceCrawlOutcomeModel.new_item_count == 0,
            SourceCrawlOutcomeModel.error.is_(None),
            SourceCrawlOutcomeModel.crawled_at >= cutoff,
        )
        return int(self._session.execute(stmt).scalar_one() or 0)

    def last_success_count(self, source_key: str) -> int | None:
        """Return the most recent successful crawl count for a source."""
        stmt = (
            select(SourceCrawlOutcomeModel.new_item_count)
            .where(
                SourceCrawlOutcomeModel.source_key == source_key,
                SourceCrawlOutcomeModel.error.is_(None),
                SourceCrawlOutcomeModel.new_item_count > 0,
            )
            .order_by(SourceCrawlOutcomeModel.crawled_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

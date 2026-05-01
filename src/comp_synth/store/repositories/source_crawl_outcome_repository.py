"""Repository for per-source crawl outcomes."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comp_synth.store.models import SourceCrawlOutcomeModel


@dataclass(frozen=True)
class SourceHealth:
    source_key: str
    source_type: str
    site_name: str
    source_url: str
    status: str
    last_crawled_at: datetime
    last_new_item_count: int
    recent_zero_days: int
    last_error: str | None = None


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

    def list_source_health(
        self,
        lookback_days: int,
        zero_day_threshold: int,
        now: datetime | None = None,
        limit: int = 100,
    ) -> list[SourceHealth]:
        """Return latest source health ordered by operational priority."""
        now = now or datetime.now()
        latest_id_subq = (
            select(func.max(SourceCrawlOutcomeModel.id))
            .group_by(SourceCrawlOutcomeModel.source_key)
            .scalar_subquery()
        )
        rows = self._session.execute(
            select(SourceCrawlOutcomeModel)
            .where(SourceCrawlOutcomeModel.id.in_(latest_id_subq))
            .order_by(SourceCrawlOutcomeModel.source_key.asc())
        ).scalars().all()

        health = [
            self._to_health(row, lookback_days, zero_day_threshold, now)
            for row in rows
        ]
        return sorted(
            health,
            key=lambda entry: (
                self._status_rank(entry.status),
                -entry.recent_zero_days,
                entry.source_key,
            ),
        )[: max(1, min(limit, 100))]

    def _to_health(
        self,
        row: SourceCrawlOutcomeModel,
        lookback_days: int,
        zero_day_threshold: int,
        now: datetime,
    ) -> SourceHealth:
        recent_zero_days = self.count_recent_zero_days(row.source_key, lookback_days=lookback_days, now=now)
        if row.error:
            status = "failed"
        elif recent_zero_days >= zero_day_threshold:
            status = "stale"
        else:
            status = "healthy"
        return SourceHealth(
            source_key=row.source_key,
            source_type=row.source_type,
            site_name=row.site_name,
            source_url=row.source_url,
            status=status,
            last_crawled_at=row.crawled_at,
            last_new_item_count=row.new_item_count,
            recent_zero_days=recent_zero_days,
            last_error=row.error,
        )

    def _status_rank(self, status: str) -> int:
        return {"failed": 0, "stale": 1, "healthy": 2}.get(status, 3)

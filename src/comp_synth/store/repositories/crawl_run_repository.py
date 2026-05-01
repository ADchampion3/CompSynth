"""Repository for crawl run status records."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from comp_synth.schema.crawl_run import CrawlRun, CrawlRunSource
from comp_synth.store.models import CrawlRunModel, CrawlRunSourceModel


class CrawlRunRepository:
    """Data access for crawl runs."""

    def __init__(self, session: Session):
        self._session = session

    def start(self, run_id: str, scope: str, now: datetime | None = None) -> CrawlRun:
        """Create a running crawl run."""
        now = now or datetime.now()
        row = CrawlRunModel(
            run_id=run_id,
            scope=scope,
            status="running",
            started_at=now,
            heartbeat_at=now,
            new_items=0,
            errors=[],
            error_text=None,
        )
        self._session.add(row)
        return self._to_domain(row)

    def finish(
        self,
        run_id: str,
        status: str,
        new_items: int = 0,
        errors: list[str] | None = None,
        error_text: str | None = None,
        now: datetime | None = None,
    ) -> CrawlRun | None:
        """Complete a crawl run."""
        row = self._session.get(CrawlRunModel, run_id)
        if row is None:
            return None
        now = now or datetime.now()
        row.status = status
        row.finished_at = now
        row.heartbeat_at = now
        row.new_items = new_items
        row.errors = errors or []
        row.error_text = error_text
        return self._to_domain(row)

    def get(self, run_id: str) -> CrawlRun | None:
        """Get one crawl run by id."""
        row = self._session.get(CrawlRunModel, run_id)
        return self._to_domain(row) if row else None

    def list_recent(self, limit: int = 20) -> list[CrawlRun]:
        """List recent crawl runs newest first."""
        stmt = select(CrawlRunModel).order_by(CrawlRunModel.started_at.desc()).limit(limit)
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def list_stale_running(
        self,
        stale_after_minutes: int,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[CrawlRun]:
        """List running crawl runs whose heartbeat is older than the threshold."""
        now = now or datetime.now()
        cutoff = now - timedelta(minutes=stale_after_minutes)
        stmt = (
            select(CrawlRunModel)
            .where(
                CrawlRunModel.status == "running",
                CrawlRunModel.heartbeat_at < cutoff,
            )
            .order_by(CrawlRunModel.heartbeat_at.asc(), CrawlRunModel.started_at.asc())
            .limit(max(1, min(limit, 100)))
        )
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def record_source(
        self,
        run_id: str,
        source_key: str,
        source_type: str,
        source_url: str,
        status: str,
        new_items: int = 0,
        error_text: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> CrawlRunSource:
        """Record one per-source child run outcome."""
        now = datetime.now()
        row = CrawlRunSourceModel(
            run_id=run_id,
            source_key=source_key,
            source_type=source_type,
            source_url=source_url,
            status=status,
            started_at=started_at or now,
            finished_at=finished_at or now,
            new_items=new_items,
            error_text=error_text,
        )
        self._session.add(row)
        return self._to_source_domain(row)

    def list_sources(self, run_id: str) -> list[CrawlRunSource]:
        """List source child runs for a crawl run."""
        stmt = (
            select(CrawlRunSourceModel)
            .where(CrawlRunSourceModel.run_id == run_id)
            .order_by(CrawlRunSourceModel.id.asc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_source_domain(row) for row in rows]

    def _to_domain(self, row: CrawlRunModel) -> CrawlRun:
        return CrawlRun(
            run_id=row.run_id,
            scope=row.scope,
            status=row.status,
            started_at=row.started_at,
            finished_at=row.finished_at,
            heartbeat_at=row.heartbeat_at,
            new_items=row.new_items,
            errors=list(row.errors or []),
            error_text=row.error_text,
        )

    def _to_source_domain(self, row: CrawlRunSourceModel) -> CrawlRunSource:
        return CrawlRunSource(
            id=row.id,
            run_id=row.run_id,
            source_key=row.source_key,
            source_type=row.source_type,
            source_url=row.source_url,
            status=row.status,
            started_at=row.started_at,
            finished_at=row.finished_at,
            new_items=row.new_items,
            error_text=row.error_text,
        )

"""Repository for generated report metadata."""

from datetime import date, datetime, time
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comp_synth.schema.report import ReportMetadata
from comp_synth.store.models import ReportModel


class ReportRepository:
    """Data access for report metadata."""

    def __init__(self, session: Session):
        self._session = session

    def save(
        self,
        report_id: str,
        title: str,
        markdown_path: Path,
        date_from: date | None = None,
        date_to: date | None = None,
        filters: dict | None = None,
        created_at: datetime | None = None,
    ) -> ReportMetadata:
        """Create or update report metadata."""
        created_at = created_at or datetime.now()
        row = self._session.get(ReportModel, report_id)
        if row is None:
            row = ReportModel(
                report_id=report_id,
                title=title,
                date_from=self._date_to_datetime(date_from),
                date_to=self._date_to_datetime(date_to),
                filters=filters or {},
                markdown_path=str(markdown_path),
                created_at=created_at,
            )
            self._session.add(row)
            return self._to_domain(row)

        row.title = title
        row.date_from = self._date_to_datetime(date_from)
        row.date_to = self._date_to_datetime(date_to)
        row.filters = filters or {}
        row.markdown_path = str(markdown_path)
        return self._to_domain(row)

    def get(self, report_id: str) -> ReportMetadata | None:
        """Get one report metadata row."""
        row = self._session.get(ReportModel, report_id)
        return self._to_domain(row) if row else None

    def list_recent(self, limit: int = 50) -> list[ReportMetadata]:
        """List recent report metadata rows."""
        stmt = select(ReportModel).order_by(ReportModel.created_at.desc(), ReportModel.report_id.desc()).limit(limit)
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def count(self) -> int:
        """Count report metadata rows."""
        return int(self._session.execute(select(func.count()).select_from(ReportModel)).scalar_one())

    def _to_domain(self, row: ReportModel) -> ReportMetadata:
        return ReportMetadata(
            report_id=row.report_id,
            title=row.title,
            markdown_path=Path(row.markdown_path),
            created_at=row.created_at,
            date_from=row.date_from.date() if row.date_from else None,
            date_to=row.date_to.date() if row.date_to else None,
            filters=dict(row.filters or {}),
        )

    def _date_to_datetime(self, value: date | None) -> datetime | None:
        if value is None:
            return None
        return datetime.combine(value, time.min)

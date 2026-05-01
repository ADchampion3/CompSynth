"""Repository for managed source configuration."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comp_synth.schema.source import SourceConfig
from comp_synth.store.models import SourceModel


class SourceRepository:
    """Data access for managed sources."""

    def __init__(self, session: Session):
        self._session = session

    def list(self, include_archived: bool = False) -> list[SourceConfig]:
        """List managed sources in stable creation order."""
        stmt = select(SourceModel).order_by(SourceModel.created_at.asc(), SourceModel.source_key.asc())
        if not include_archived:
            stmt = stmt.where(SourceModel.archived_at.is_(None))
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def count(self, include_archived: bool = False) -> int:
        """Count managed sources."""
        stmt = select(func.count()).select_from(SourceModel)
        if not include_archived:
            stmt = stmt.where(SourceModel.archived_at.is_(None))
        return int(self._session.execute(stmt).scalar_one())

    def save(self, source: SourceConfig, now: datetime | None = None) -> None:
        """Create or update a managed source by stable source key."""
        now = now or datetime.now()
        stmt = select(SourceModel).where(SourceModel.source_key == source.source_key)
        existing = self._session.execute(stmt).scalar_one_or_none()
        if existing:
            existing.name = source.name
            existing.source_type = source.source_type
            existing.url = source.url
            existing.enabled = 1 if source.enabled else 0
            existing.selectors = source.selectors
            existing.javascript = 1 if source.javascript else 0
            existing.crawl_frequency = str((source.raw_config or {}).get("crawl_frequency", "manual"))
            existing.priority = str((source.raw_config or {}).get("priority", "normal"))
            existing.updated_at = now
            existing.raw_config = source.raw_config or {}
            existing.archived_at = None
            return

        raw_config = source.raw_config or {}
        self._session.add(
            SourceModel(
                source_key=source.source_key,
                name=source.name,
                source_type=source.source_type,
                url=source.url,
                enabled=1 if source.enabled else 0,
                selectors=source.selectors,
                javascript=1 if source.javascript else 0,
                crawl_frequency=str(raw_config.get("crawl_frequency", "manual")),
                priority=str(raw_config.get("priority", "normal")),
                archived_at=None,
                created_at=now,
                updated_at=now,
                raw_config=raw_config,
            )
        )

    def _to_domain(self, row: SourceModel) -> SourceConfig:
        raw_config = dict(row.raw_config) if row.raw_config else {}
        raw_config.update(
            {
                "type": row.source_type,
                "url": row.url,
                "enabled": bool(row.enabled),
            }
        )
        if row.name:
            raw_config["name"] = row.name
        if row.selectors is not None:
            raw_config["selectors"] = row.selectors
        if row.javascript:
            raw_config["javascript"] = True
        raw_config["crawl_frequency"] = row.crawl_frequency
        raw_config["priority"] = row.priority

        return SourceConfig(
            source_key=row.source_key,
            source_type=row.source_type,
            url=row.url,
            name=row.name,
            enabled=bool(row.enabled),
            selectors=row.selectors,
            javascript=bool(row.javascript),
            raw_config=raw_config,
        )

"""SiteSchema repository - data access layer for site schemas."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from comp_synth.schema.site_chema import SiteSchema
from comp_synth.store.models import SiteSchemaModel


class SiteSchemaRepository:
    """Repository for SiteSchemaModel <-> SiteSchema mapping."""

    def __init__(self, session: Session):
        self._session = session

    def _to_model(self, schema: SiteSchema) -> SiteSchemaModel:
        """Convert SiteSchema Pydantic model to SiteSchemaModel ORM object."""
        return SiteSchemaModel(
            site_name=schema.site_name,
            site_url=schema.site_url,
            selectors=schema.selectors,
            created_at=schema.created_at,
            updated_at=schema.updated_at,
            last_llm_call=schema.last_llm_call,
            list_selectors={},
        )

    def _to_domain(self, row: SiteSchemaModel) -> SiteSchema:
        """Convert SiteSchemaModel ORM object to SiteSchema Pydantic model."""
        return SiteSchema(
            site_name=row.site_name,
            site_url=row.site_url,
            selectors=row.selectors,
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_llm_call=row.last_llm_call,
        )

    def get(self, sname: str) -> SiteSchema | None:
        """Get a SiteSchema by site name."""
        stmt = select(SiteSchemaModel).where(SiteSchemaModel.site_name == sname)
        row = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(row) if row else None

    def save(self, schema: SiteSchema) -> None:
        """Save or update a SiteSchema."""
        stmt = select(SiteSchemaModel).where(SiteSchemaModel.site_name == schema.site_name)
        existing = self._session.execute(stmt).scalar_one_or_none()
        now = datetime.now()

        if existing:
            existing.site_url = schema.site_url
            existing.selectors = schema.selectors
            existing.updated_at = now
            existing.last_llm_call = schema.last_llm_call
        else:
            model = self._to_model(schema)
            model.created_at = now
            model.updated_at = now
            self._session.add(model)

    def can_use_llm(self, sname: str) -> bool:
        """Check if LLM can be called for this site (rate limit: once per 24 hours)."""
        stmt = select(SiteSchemaModel).where(SiteSchemaModel.site_name == sname)
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None or row.last_llm_call is None:
            return True
        return (datetime.now() - row.last_llm_call) > timedelta(hours=24)

    def mark_llm_called(self, sname: str) -> None:
        """Mark that LLM was called for this site."""
        stmt = select(SiteSchemaModel).where(SiteSchemaModel.site_name == sname)
        row = self._session.execute(stmt).scalar_one_or_none()
        if row:
            row.last_llm_call = datetime.now()
            row.updated_at = datetime.now()

    def update_selectors(self, sname: str, selectors: list[dict[str, str]]) -> None:
        """Update the selectors for a site."""
        stmt = select(SiteSchemaModel).where(SiteSchemaModel.site_name == sname)
        row = self._session.execute(stmt).scalar_one_or_none()
        if row:
            row.selectors = selectors
            row.updated_at = datetime.now()

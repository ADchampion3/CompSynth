"""Repository for per-domain proxy requirement state."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from comp_synth.store.models import DomainProxyStateModel

FAILURE_THRESHOLD = 2


@dataclass(frozen=True)
class DomainProxyEntry:
    domain: str
    needs_proxy: bool
    failure_count: int
    last_failure_at: datetime | None
    last_failure_error: str | None
    detected_at: datetime | None


class DomainProxyRepository:
    """Data access for domain proxy state."""

    def __init__(self, session: Session):
        self._session = session

    def needs_proxy(self, domain: str) -> bool:
        stmt = select(DomainProxyStateModel.needs_proxy).where(
            DomainProxyStateModel.domain == domain,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return row == 1 if row is not None else False

    def record_failure(self, domain: str, error: str) -> None:
        existing = self._session.get(DomainProxyStateModel, domain)
        now = datetime.now()
        if existing:
            existing.failure_count += 1
            existing.last_failure_at = now
            existing.last_failure_error = error[:500]
            existing.updated_at = now
            if existing.failure_count >= FAILURE_THRESHOLD and not existing.needs_proxy:
                existing.needs_proxy = 1
                existing.detected_at = now
        else:
            self._session.add(DomainProxyStateModel(
                domain=domain,
                needs_proxy=0,
                failure_count=1,
                last_failure_at=now,
                last_failure_error=error[:500],
                updated_at=now,
            ))

    def record_success(self, domain: str) -> None:
        existing = self._session.get(DomainProxyStateModel, domain)
        if existing:
            existing.failure_count = 0
            existing.updated_at = datetime.now()

    def clear_proxy_need(self, domain: str) -> None:
        existing = self._session.get(DomainProxyStateModel, domain)
        if existing:
            existing.needs_proxy = 0
            existing.failure_count = 0
            existing.updated_at = datetime.now()

    def list_all(self) -> list[DomainProxyEntry]:
        rows = self._session.execute(
            select(DomainProxyStateModel).order_by(DomainProxyStateModel.domain)
        ).scalars().all()
        return [
            DomainProxyEntry(
                domain=r.domain,
                needs_proxy=bool(r.needs_proxy),
                failure_count=r.failure_count,
                last_failure_at=r.last_failure_at,
                last_failure_error=r.last_failure_error,
                detected_at=r.detected_at,
            )
            for r in rows
        ]

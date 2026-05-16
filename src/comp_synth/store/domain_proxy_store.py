"""Domain proxy state storage."""

from comp_synth.config import settings
from comp_synth.store.database import get_engine
from comp_synth.store.repositories.domain_proxy_repository import DomainProxyRepository


class DomainProxyStore:
    """SQLite-backed domain proxy state store."""

    def __init__(self):
        self._engine, self._session_factory = get_engine(settings.crawl_db_path, "crawl_state.db")

    def _with_session(self, fn):
        with self._session_factory() as session:
            result = fn(DomainProxyRepository(session))
            session.commit()
            return result

    def needs_proxy(self, domain: str) -> bool:
        return self._with_session(lambda repo: repo.needs_proxy(domain))

    def record_failure(self, domain: str, error: str) -> None:
        self._with_session(lambda repo: repo.record_failure(domain, error))

    def record_success(self, domain: str) -> None:
        self._with_session(lambda repo: repo.record_success(domain))

    def clear_proxy_need(self, domain: str) -> None:
        self._with_session(lambda repo: repo.clear_proxy_need(domain))

    def list_all(self):
        return self._with_session(lambda repo: repo.list_all())

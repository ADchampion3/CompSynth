"""Source crawl outcome storage and selector health queries."""

from urllib.parse import urlparse

from comp_synth.config import settings
from comp_synth.store.database import get_engine
from comp_synth.store.repositories.source_crawl_outcome_repository import (
    SourceCrawlOutcomeRepository,
)


class SourceOutcomeStore:
    """SQLite-backed source crawl outcome store."""

    def __init__(self):
        self._engine, self._session_factory = get_engine(settings.crawl_db_path, "crawl_state.db")

    def _with_session(self, fn):
        with self._session_factory() as session:
            result = fn(SourceCrawlOutcomeRepository(session))
            session.commit()
            return result

    def record_source_outcome(self, source: dict, count: int, error: str | None) -> None:
        """Record the final outcome for one configured source."""
        source_url = source.get("url", "")
        source_key = source.get("name") or source_url
        site_name = urlparse(source_url).netloc or "unknown"
        source_type = source.get("type", "unknown")
        self._with_session(
            lambda repo: repo.record(
                source_key=source_key,
                source_type=source_type,
                site_name=site_name,
                source_url=source_url,
                new_item_count=count,
                error=error,
            )
        )

    def should_refresh_selectors(self, source_key: str | None, source_type: str) -> bool:
        """Return true when recent zero-result days meet the refresh threshold."""
        if not source_key or not settings.selector_zero_refresh_enabled:
            return False
        if source_type not in {"web", "javascript"}:
            return False

        zero_days = self._with_session(
            lambda repo: repo.count_recent_zero_days(
                source_key,
                lookback_days=settings.selector_zero_refresh_lookback_days,
            )
        )
        return zero_days >= settings.selector_zero_refresh_days

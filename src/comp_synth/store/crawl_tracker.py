"""Crawl tracker - article metadata storage and deduplication via SQLite."""

from datetime import datetime, timezone

from comp_synth.config import settings
from comp_synth.schema.content_item import ContentItem
from comp_synth.store.database import get_engine
from comp_synth.store.repositories.article_repository import ArticleRepository
from comp_synth.store.repositories.crawl_run_repository import CrawlRunRepository


class CrawlTracker:
    """Crawl state tracking and deduplication using SQLite + SQLAlchemy."""

    def __init__(self):
        self._engine, self._session_factory = get_engine(settings.crawl_db_path, "crawl_state.db")
        self._crawled_urls: set[str] | None = None

    def _with_session(self, fn):
        """Execute a function within a session context."""
        with self._session_factory() as session:
            result = fn(ArticleRepository(session))
            session.commit()
            return result

    def preload_crawled_urls(self) -> None:
        """Load all article IDs into memory for fast dedup checks."""
        if self._crawled_urls is not None:
            return
        self._crawled_urls = set(self._with_session(lambda repo: repo.get_all_article_ids()))

    def is_crawled(self, source: str, url: str) -> bool:
        """Check if URL has already been crawled. Uses in-memory cache when available."""
        aid = f"{source}:{url}"
        if self._crawled_urls is not None:
            return aid in self._crawled_urls
        return self._with_session(lambda repo: repo.is_crawled(source, url))

    def get_last_crawl_time(self, source: str, feed_url: str) -> datetime | None:
        """Get the most recent crawl time for a given source and feed URL."""
        return self._with_session(lambda repo: repo.get_last_crawl_time(source, feed_url))

    def get_today_items(self, source: str) -> list[dict]:
        """Get all items crawled today for a given source."""
        with self._session_factory() as session:
            repo = ArticleRepository(session)
            items = repo.get_today_items(source)
            return [
                {
                    "article_id": item.article_id,
                    "source": item.source,
                    "url": item.url,
                    "crawled_at": item.crawled_at.isoformat() if item.crawled_at else "",
                    "summary": item.summary,
                    "title": item.title,
                    "metadata": item.extra_metadata,
                    "content": item.content,
                }
                for item in items
            ]

    def get_today_items_all_sources(self) -> list[dict]:
        """Get all items crawled today across all sources (single query)."""
        with self._session_factory() as session:
            repo = ArticleRepository(session)
            items = repo.get_today_items_all_sources()
            return [
                {
                    "article_id": item.article_id,
                    "source": item.source,
                    "url": item.url,
                    "crawled_at": item.crawled_at.isoformat() if item.crawled_at else "",
                    "summary": item.summary,
                    "title": item.title,
                    "metadata": item.extra_metadata,
                    "content": item.content,
                }
                for item in items
            ]

    def save_article(
        self,
        article_id: str,
        title: str,
        summary: str,
        content: str = "",
        metadata: dict | None = None,
        published_at: str | None = None,
    ) -> None:
        """Save article metadata to SQLite."""
        source, url = article_id.split(":", 1) if ":" in article_id else ("unknown", article_id)
        item = ContentItem(
            id=article_id,
            source=source,
            url=url,
            title=title,
            summary=summary,
            content=content,
            metadata=metadata or {},
            published_at=datetime.fromisoformat(published_at) if published_at else None,
            collected_at=datetime.now(timezone.utc),
        )
        self._with_session(lambda repo: repo.save(item))

    def save_articles(self, items: list[ContentItem]) -> None:
        """Batch save article metadata to SQLite."""
        if not items:
            return
        with self._session_factory() as session:
            repo = ArticleRepository(session)
            for item in items:
                repo.save(item)
                if self._crawled_urls is not None:
                    self._crawled_urls.add(item.id)
            session.commit()

    def get_article_by_id(self, article_id: str) -> dict | None:
        """Get article metadata by article_id."""
        with self._session_factory() as session:
            repo = ArticleRepository(session)
            item = repo.get_by_id(article_id)
            if item is None:
                return None
            return {
                "article_id": item.id,
                "source": item.source,
                "url": item.url,
                "title": item.title,
                "summary": item.summary,
                "content": item.content,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "crawled_at": item.collected_at.isoformat(),
                "metadata": item.metadata,
            }

    def get_articles_by_ids(self, article_ids: list[str]) -> list[dict]:
        """Batch get article metadata by article_ids."""
        if not article_ids:
            return []
        with self._session_factory() as session:
            repo = ArticleRepository(session)
            items = repo.get_by_ids(article_ids)
            return [
                {
                    "article_id": item.id,
                    "source": item.source,
                    "url": item.url,
                    "title": item.title,
                    "summary": item.summary,
                    "content": item.content,
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                    "crawled_at": item.collected_at.isoformat(),
                    "metadata": item.metadata,
                }
                for item in items
            ]

    def get_expired_article_ids(self, ttl_days: int = 30) -> list[str]:
        """Get article IDs older than TTL for vector store cleanup."""
        return self._with_session(lambda repo: repo.get_expired_article_ids(ttl_days))

    # -- Crawl run checkpoint helpers --

    def start_crawl_run(self, run_id: str, scope: str = "full") -> None:
        """Start a new crawl run for checkpoint tracking."""
        with self._session_factory() as session:
            repo = CrawlRunRepository(session)
            repo.start(run_id, scope)
            session.commit()

    def finish_crawl_run(self, run_id: str, status: str, new_items: int = 0, errors: list[str] | None = None) -> None:
        """Finish a crawl run."""
        with self._session_factory() as session:
            repo = CrawlRunRepository(session)
            repo.finish(run_id, status, new_items=new_items, errors=errors)
            session.commit()

    def record_source_in_run(
        self,
        run_id: str,
        source_key: str,
        source_type: str,
        source_url: str,
        status: str,
        new_items: int = 0,
        error_text: str | None = None,
    ) -> None:
        """Record per-source outcome for the current crawl run."""
        with self._session_factory() as session:
            repo = CrawlRunRepository(session)
            repo.record_source(
                run_id, source_key, source_type, source_url, status,
                new_items=new_items, error_text=error_text,
            )
            session.commit()

    def get_completed_source_keys(self, run_id: str) -> set[str]:
        """Get source keys already completed in the current run."""
        with self._session_factory() as session:
            repo = CrawlRunRepository(session)
            sources = repo.list_sources(run_id)
            return {s.source_key for s in sources if s.status in ("completed", "error")}

    def set_liked(self, source: str, url: str, liked: bool = True) -> None:
        """Set or unset the liked status of an article."""
        self._with_session(lambda repo: repo.set_liked(source, url, liked))

    def get_liked_items(self) -> list[dict]:
        """Get all liked articles."""
        with self._session_factory() as session:
            repo = ArticleRepository(session)
            items = repo.get_liked_items()
            return [
                {
                    "article_id": item.id,
                    "source": item.source,
                    "url": item.url,
                    "title": item.title,
                    "summary": item.summary,
                    "content": item.content,
                    "crawled_at": item.collected_at.isoformat(),
                    "metadata": item.metadata,
                }
                for item in items
            ]

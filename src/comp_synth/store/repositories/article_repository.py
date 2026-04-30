"""Article repository - data access layer for articles."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comp_synth.schema.content_item import ContentItem
from comp_synth.store.models import ArticleModel


class ArticleRepository:
    """Repository for ArticleModel <-> ContentItem mapping."""

    def __init__(self, session: Session):
        self._session = session

    def _to_model(self, item: ContentItem) -> ArticleModel:
        """Convert ContentItem Pydantic model to ArticleModel ORM object."""
        metadata = {**item.metadata, "tags": item.tags}
        return ArticleModel(
            article_id=item.id,
            vector_id=item.id,
            crawled_at=item.collected_at,
            published_at=item.published_at,
            content=item.content,
            summary=item.summary,
            title=item.title,
            url=item.url,
            source=item.source,
            extra_metadata=metadata,
            liked=0,
        )

    def _to_domain(self, row: ArticleModel) -> ContentItem:
        """Convert ArticleModel ORM object to ContentItem Pydantic model."""
        metadata = dict(row.extra_metadata) if row.extra_metadata else {}
        tags = metadata.pop("tags", ["其他"])
        return ContentItem(
            id=row.article_id,
            source=row.source,
            url=row.url,
            title=row.title,
            summary=row.summary,
            content=row.content,
            tags=tags,
            published_at=row.published_at,
            collected_at=row.crawled_at,
            metadata=metadata,
        )

    def save(self, item: ContentItem) -> None:
        """Save or update a ContentItem."""
        stmt = select(ArticleModel).where(ArticleModel.article_id == item.id)
        existing = self._session.execute(stmt).scalar_one_or_none()
        if existing:
            existing.vector_id = item.id
            existing.crawled_at = item.collected_at
            existing.published_at = item.published_at
            existing.content = item.content
            existing.summary = item.summary
            existing.title = item.title
            existing.url = item.url
            existing.source = item.source
            existing.extra_metadata = item.metadata
        else:
            self._session.add(self._to_model(item))

    def get_by_id(self, aid: str) -> ContentItem | None:
        """Get a ContentItem by its article_id."""
        stmt = select(ArticleModel).where(ArticleModel.article_id == aid)
        row = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(row) if row else None

    def get_by_ids(self, article_ids: list[str]) -> list[ContentItem]:
        """Get multiple ContentItems by their article_ids."""
        if not article_ids:
            return []
        stmt = select(ArticleModel).where(ArticleModel.article_id.in_(article_ids))
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def is_crawled(self, source: str, url: str) -> bool:
        """Check if a URL has already been crawled."""
        aid = f"{source}:{url}"
        stmt = select(ArticleModel.article_id).where(ArticleModel.article_id == aid)
        return self._session.execute(stmt).scalar_one_or_none() is not None

    def get_today_items(self, source: str) -> list[ArticleModel]:
        """Get all items crawled today for a given source."""
        today = datetime.now(timezone.utc).date()
        stmt = select(ArticleModel).where(
            ArticleModel.source == source,
            ArticleModel.crawled_at
            >= datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc),
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_expired_article_ids(self, ttl_days: int = 30) -> list[str]:
        """Get article IDs older than TTL days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
        stmt = select(ArticleModel.article_id).where(ArticleModel.crawled_at < cutoff)
        return list(self._session.execute(stmt).scalars().all())

    def set_liked(self, source: str, url: str, liked: bool = True) -> None:
        """Set or unset the liked status of an article."""
        aid = f"{source}:{url}"
        stmt = select(ArticleModel).where(ArticleModel.article_id == aid)
        row = self._session.execute(stmt).scalar_one_or_none()
        if row:
            row.liked = 1 if liked else 0

    def get_liked_items(self) -> list[ContentItem]:
        """Get all liked articles."""
        stmt = select(ArticleModel).where(ArticleModel.liked == 1)
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def get_last_crawl_time(self, source: str, feed_url: str) -> datetime | None:
        """Get the most recent crawl time for a given source and feed URL."""
        stmt = (
            select(func.max(ArticleModel.crawled_at))
            .where(ArticleModel.source == source)
        )
        rows = list(self._session.execute(stmt).scalars().all())
        return rows[0] if rows and rows[0] is not None else None

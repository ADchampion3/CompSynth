"""Article repository - data access layer for articles."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import String as SqlString
from sqlalchemy import cast, func, or_, select
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
        metadata["_liked"] = row.liked
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
            existing.extra_metadata = {**item.metadata, "tags": item.tags}
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

    def list_recent(
        self,
        limit: int = 50,
        offset: int = 0,
        source: str | None = None,
        tag: str | None = None,
        liked: bool | None = None,
        query: str | None = None,
    ) -> list[ContentItem]:
        """List articles ordered by crawl time, newest first."""
        stmt = self._filtered_select(source=source, tag=tag, liked=liked, query=query)
        stmt = stmt.order_by(ArticleModel.crawled_at.desc(), ArticleModel.article_id.asc()).limit(limit).offset(offset)
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def count(
        self,
        source: str | None = None,
        tag: str | None = None,
        liked: bool | None = None,
        query: str | None = None,
    ) -> int:
        """Count stored articles."""
        stmt = self._filtered_select(
            select(func.count()).select_from(ArticleModel),
            source=source,
            tag=tag,
            liked=liked,
            query=query,
        )
        return int(self._session.execute(stmt).scalar_one())

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _filtered_select(
        self,
        stmt=None,
        source: str | None = None,
        tag: str | None = None,
        liked: bool | None = None,
        query: str | None = None,
    ):
        if stmt is None:
            stmt = select(ArticleModel)
        if source:
            stmt = stmt.where(ArticleModel.source == source)
        if tag:
            escaped = self._escape_like(tag)
            encoded_tag = json.dumps(tag, ensure_ascii=True).strip('"')
            encoded_escaped = self._escape_like(encoded_tag)
            metadata_text = cast(ArticleModel.extra_metadata, SqlString)
            stmt = stmt.where(
                or_(
                    metadata_text.like(f"%{escaped}%", escape="\\"),
                    metadata_text.like(f"%{encoded_escaped}%", escape="\\"),
                )
            )
        if liked is not None:
            stmt = stmt.where(ArticleModel.liked == (1 if liked else 0))
        if query:
            escaped_query = self._escape_like(query)
            pattern = f"%{escaped_query}%"
            stmt = stmt.where(
                or_(
                    ArticleModel.title.ilike(pattern, escape="\\"),
                    ArticleModel.summary.ilike(pattern, escape="\\"),
                    ArticleModel.content.ilike(pattern, escape="\\"),
                )
            )
        return stmt

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

    def set_liked_by_id(self, article_id: str, liked: bool = True) -> bool:
        """Set or unset liked status by article id."""
        stmt = select(ArticleModel).where(ArticleModel.article_id == article_id)
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return False
        row.liked = 1 if liked else 0
        return True

    def get_liked_items(self) -> list[ContentItem]:
        """Get all liked articles."""
        stmt = select(ArticleModel).where(ArticleModel.liked == 1)
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def get_last_crawl_time(self, source: str, feed_url: str) -> datetime | None:
        """Get the most recent crawl time for a given source and feed URL."""
        stmt = select(func.max(ArticleModel.crawled_at)).where(ArticleModel.source == source)
        if feed_url:
            stmt = stmt.where(ArticleModel.extra_metadata["feed_url"].as_string() == feed_url)
        rows = list(self._session.execute(stmt).scalars().all())
        return rows[0] if rows and rows[0] is not None else None

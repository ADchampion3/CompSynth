"""Article repository - data access layer for articles."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from comp_synth.schema.content_item import ContentItem
from comp_synth.store.models import ArticleModel, ArticleStateModel


class ArticleRepository:
    """Repository for ArticleModel <-> ContentItem mapping."""

    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _parse_tags(tags_json: str | None) -> list[str]:
        if not tags_json:
            return ["其他"]
        try:
            parsed = json.loads(tags_json)
            return parsed if isinstance(parsed, list) and parsed else ["其他"]
        except (json.JSONDecodeError, TypeError):
            return ["其他"]

    def _to_model(self, item: ContentItem) -> ArticleModel:
        """Convert ContentItem Pydantic model to ArticleModel ORM object."""
        return ArticleModel(
            article_id=item.id,
            vector_id=item.id,
            source_key=item.metadata.get("source_key", item.source),
            crawled_at=item.collected_at,
            published_at=item.published_at,
            content=item.content,
            summary=item.summary,
            title=item.title,
            url=item.url,
            source=item.source,
            extra_metadata=item.metadata,
            tags=json.dumps(item.tags, ensure_ascii=False),
            liked=0,
        )

    def _to_domain(self, row: ArticleModel) -> ContentItem:
        """Convert ArticleModel ORM object to ContentItem Pydantic model."""
        metadata = dict(row.extra_metadata) if row.extra_metadata else {}
        metadata["_liked"] = row.liked
        tags = self._parse_tags(row.tags)
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
        """Save or update a ContentItem. Preserves user-edited tags on update."""
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
            # Preserve user-edited tags; only set tags on first save
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
        read_state: str | None = None,
    ) -> list[ContentItem]:
        """List articles ordered by crawl time, newest first."""
        stmt = self._filtered_select(source=source, tag=tag, liked=liked, query=query, read_state=read_state)
        stmt = stmt.order_by(ArticleModel.crawled_at.desc(), ArticleModel.article_id.asc()).limit(limit).offset(offset)
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def count(
        self,
        source: str | None = None,
        tag: str | None = None,
        liked: bool | None = None,
        query: str | None = None,
        read_state: str | None = None,
    ) -> int:
        """Count stored articles."""
        stmt = self._filtered_select(
            select(func.count()).select_from(ArticleModel),
            source=source,
            tag=tag,
            liked=liked,
            query=query,
            read_state=read_state,
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
        read_state: str | None = None,
    ):
        if stmt is None:
            stmt = select(ArticleModel)
        if source:
            stmt = stmt.where(ArticleModel.source_key == source)
        if tag:
            stmt = stmt.where(
                or_(
                    text("EXISTS (SELECT 1 FROM json_each(tags) WHERE value = :tag)").bindparams(tag=tag),
                    text("EXISTS (SELECT 1 FROM json_each(json_extract(extra_metadata, '$.tags')) WHERE value = :tag2)").bindparams(tag2=tag),
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
        if read_state is not None:
            stmt = stmt.outerjoin(
                ArticleStateModel,
                ArticleModel.article_id == ArticleStateModel.article_id,
            )
            if read_state == "unread":
                stmt = stmt.where(
                    or_(
                        ArticleStateModel.read_state == "unread",
                        ArticleStateModel.article_id.is_(None),
                    )
                )
            else:
                stmt = stmt.where(ArticleStateModel.read_state == read_state)
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

    def get_today_items_all_sources(self) -> list[ArticleModel]:
        """Get all items crawled today across all sources (single query)."""
        today = datetime.now(timezone.utc).date()
        stmt = select(ArticleModel).where(
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

    def update_tags(self, article_id: str, tags: list[str]) -> bool:
        """Update tags for an article. Returns False if article not found."""
        stmt = select(ArticleModel).where(ArticleModel.article_id == article_id)
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return False
        row.tags = json.dumps(tags, ensure_ascii=False)
        return True

    def get_tag_vocabulary(self) -> list[str]:
        """Get distinct tags across all articles."""
        rows = self._session.execute(
            text(
                "SELECT DISTINCT value FROM ("
                "  SELECT j.value FROM articles a, json_each(a.tags) j "
                "  UNION "
                "  SELECT j.value FROM articles a, json_each(json_extract(a.extra_metadata, '$.tags')) j"
                ") ORDER BY value"
            )
        ).scalars().all()
        return list(rows)

    def get_liked_items(self) -> list[ContentItem]:
        """Get all liked articles."""
        stmt = select(ArticleModel).where(ArticleModel.liked == 1)
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    def get_last_crawl_time(self, source: str, feed_url: str) -> datetime | None:
        """Get the most recent crawl time for a given source and feed URL."""
        stmt = select(func.max(ArticleModel.crawled_at)).where(ArticleModel.source_key == source)
        if feed_url:
            stmt = stmt.where(ArticleModel.extra_metadata["feed_url"].as_string() == feed_url)
        rows = list(self._session.execute(stmt).scalars().all())
        return rows[0] if rows and rows[0] is not None else None

    def get_all_article_ids(self) -> list[str]:
        """Get all article IDs for in-memory dedup cache."""
        stmt = select(ArticleModel.article_id)
        return list(self._session.execute(stmt).scalars().all())

    def get_distinct_sources(self) -> list[str]:
        """Get distinct source keys that have at least one article."""
        rows = self._session.execute(
            select(ArticleModel.source_key).distinct().order_by(ArticleModel.source_key.asc())
        ).scalars().all()
        return list(rows)

    def get_distinct_sources_with_counts(self) -> list[tuple[str, int]]:
        """Get distinct sources with their article counts."""
        rows = self._session.execute(
            select(ArticleModel.source_key, func.count())
            .select_from(ArticleModel)
            .group_by(ArticleModel.source_key)
            .order_by(ArticleModel.source_key.asc())
        ).all()
        return [(r[0], r[1]) for r in rows]

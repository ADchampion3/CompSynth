"""Article application service."""

from dataclasses import dataclass
from datetime import datetime, timezone

from comp_synth.schema.content_item import ContentItem
from comp_synth.store.repositories.article_repository import ArticleRepository
from comp_synth.store.repositories.article_state_repository import (
    ArticleState,
    ArticleStateRepository,
)


@dataclass(frozen=True)
class ArticlePage:
    """A paginated article result."""

    items: list[ContentItem]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class ImportantArticle:
    """Article plus computed triage score."""

    article: ContentItem
    importance_score: float


class ArticleService:
    """Use-case boundary for article reads and future article state actions."""

    def __init__(
        self,
        repository: ArticleRepository,
        state_repository: ArticleStateRepository | None = None,
    ):
        self._repository = repository
        self._state_repository = state_repository

    def list_articles(
        self,
        limit: int = 50,
        offset: int = 0,
        source: str | None = None,
        tag: str | None = None,
        liked: bool | None = None,
        query: str | None = None,
        read_state: str | None = None,
    ) -> ArticlePage:
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)
        normalized_query = query.strip() if query else None
        return ArticlePage(
            items=self._repository.list_recent(
                limit=safe_limit,
                offset=safe_offset,
                source=source,
                tag=tag,
                liked=liked,
                query=normalized_query,
                read_state=read_state,
            ),
            total=self._repository.count(source=source, tag=tag, liked=liked, query=normalized_query, read_state=read_state),
            limit=safe_limit,
            offset=safe_offset,
        )

    def get_article(self, article_id: str) -> ContentItem | None:
        return self._repository.get_by_id(article_id)

    def batch_get_read_states(self, article_ids: list[str]) -> dict[str, str]:
        """Batch-fetch read states for given article IDs."""
        if self._state_repository is None or not article_ids:
            return {}
        return self._state_repository.get_read_states(article_ids)

    def set_liked(self, article_id: str, liked: bool) -> bool:
        return self._repository.set_liked_by_id(article_id, liked)

    def get_article_state(self, article_id: str) -> ArticleState | None:
        if self._state_repository is None or self.get_article(article_id) is None:
            return None
        return self._state_repository.get_or_create(article_id)

    def set_read_state(self, article_id: str, read_state: str) -> bool:
        if self._state_repository is None or self.get_article(article_id) is None:
            return False
        self._state_repository.set_read_state(article_id, read_state)
        return True

    def save_note(self, article_id: str, user_note: str) -> bool:
        if self._state_repository is None or self.get_article(article_id) is None:
            return False
        self._state_repository.save_note(article_id, user_note)
        return True

    def list_important_unread(self, limit: int = 20) -> list[ImportantArticle]:
        """Return unread articles ordered by a lightweight importance score."""
        safe_limit = max(1, min(limit, 100))
        liked_ids = {item.id for item in self._repository.get_liked_items()}
        candidates = self._repository.list_recent(limit=500, offset=0)
        important = [
            ImportantArticle(article=item, importance_score=self._importance_score(item, liked_ids))
            for item in candidates
            if self._is_unread_for_triage(item.id)
        ]
        return sorted(
            important,
            key=lambda entry: (
                entry.importance_score,
                entry.article.collected_at,
                entry.article.id,
            ),
            reverse=True,
        )[:safe_limit]

    def _is_unread_for_triage(self, article_id: str) -> bool:
        if self._state_repository is None:
            return True
        state = self._state_repository.get(article_id)
        return state is None or state.read_state in {"unread", "later"}

    def _importance_score(self, item: ContentItem, liked_ids: set[str]) -> float:
        score = 1.0
        if item.id in liked_ids:
            score += 5.0

        normalized_tags = {tag.strip().lower() for tag in item.tags}
        if normalized_tags.intersection({"ai", "llm", "research", "security"}):
            score += 2.0

        collected_at = item.collected_at
        if collected_at.tzinfo is None:
            collected_at = collected_at.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - collected_at).total_seconds() / 86400)
        score += max(0.0, 2.0 - min(age_days, 7.0) * 0.25)
        return round(score, 4)

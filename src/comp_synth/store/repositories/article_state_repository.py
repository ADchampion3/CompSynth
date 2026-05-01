"""Article reading-state repository."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from comp_synth.store.models import ArticleStateModel

READ_STATES = frozenset({"unread", "read", "later", "ignored"})


class InvalidArticleStateError(ValueError):
    pass


@dataclass(frozen=True)
class ArticleState:
    article_id: str
    read_state: str
    user_note: str
    last_viewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ArticleStateRepository:
    """Persistence boundary for user article state."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, article_id: str) -> ArticleState | None:
        row = self._session.execute(
            select(ArticleStateModel).where(ArticleStateModel.article_id == article_id)
        ).scalar_one_or_none()
        return self._to_domain(row) if row else None

    def get_or_create(self, article_id: str) -> ArticleState:
        row = self._get_or_create_row(article_id)
        self._session.flush()
        return self._to_domain(row)

    def set_read_state(self, article_id: str, read_state: str) -> ArticleState:
        if read_state not in READ_STATES:
            raise InvalidArticleStateError(f"Invalid read state: {read_state}")

        row = self._get_or_create_row(article_id)
        row.read_state = read_state
        row.updated_at = self._now()
        self._session.flush()
        return self._to_domain(row)

    def save_note(self, article_id: str, user_note: str) -> ArticleState:
        row = self._get_or_create_row(article_id)
        row.user_note = user_note
        row.updated_at = self._now()
        self._session.flush()
        return self._to_domain(row)

    def mark_viewed(self, article_id: str, viewed_at: datetime | None = None) -> ArticleState:
        row = self._get_or_create_row(article_id)
        row.read_state = "read"
        row.last_viewed_at = viewed_at or self._now()
        row.updated_at = self._now()
        self._session.flush()
        return self._to_domain(row)

    def _get_or_create_row(self, article_id: str) -> ArticleStateModel:
        row = self._session.execute(
            select(ArticleStateModel).where(ArticleStateModel.article_id == article_id)
        ).scalar_one_or_none()
        if row:
            return row

        now = self._now()
        row = ArticleStateModel(
            article_id=article_id,
            read_state="unread",
            user_note="",
            last_viewed_at=None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        return row

    def _to_domain(self, row: ArticleStateModel) -> ArticleState:
        return ArticleState(
            article_id=row.article_id,
            read_state=row.read_state,
            user_note=row.user_note,
            last_viewed_at=row.last_viewed_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

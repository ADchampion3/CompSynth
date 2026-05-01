from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from comp_synth.store.models import Base
from comp_synth.store.repositories.article_state_repository import (
    ArticleStateRepository,
    InvalidArticleStateError,
)


def make_repo() -> ArticleStateRepository:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return ArticleStateRepository(Session())


def test_get_or_create_defaults_to_unread_state():
    repo = make_repo()

    state = repo.get_or_create("article-1")

    assert state.article_id == "article-1"
    assert state.read_state == "unread"
    assert state.user_note == ""
    assert state.last_viewed_at is None


def test_update_read_state_validates_allowed_values():
    repo = make_repo()

    updated = repo.set_read_state("article-1", "later")

    assert updated.read_state == "later"

    with pytest.raises(InvalidArticleStateError):
        repo.set_read_state("article-1", "archived")


def test_save_note_and_mark_viewed_persist_user_state():
    repo = make_repo()
    viewed_at = datetime(2026, 5, 1, 12, 0, 0)

    repo.save_note("article-1", "Useful context")
    state = repo.mark_viewed("article-1", viewed_at=viewed_at)

    assert state.read_state == "read"
    assert state.user_note == "Useful context"
    assert state.last_viewed_at == viewed_at

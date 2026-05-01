from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from comp_synth.schema.content_item import ContentItem
from comp_synth.services.article_service import ArticleService
from comp_synth.store.models import Base
from comp_synth.store.repositories.article_repository import ArticleRepository
from comp_synth.store.repositories.article_state_repository import (
    ArticleStateRepository,
)


def make_service_with_items(items: list[ContentItem]) -> ArticleService:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    repo = ArticleRepository(session)
    for item in items:
        repo.save(item)
    session.commit()
    return ArticleService(repo, ArticleStateRepository(session))


def test_list_articles_returns_newest_first_with_pagination():
    now = datetime.now(timezone.utc)
    service = make_service_with_items(
        [
            ContentItem(
                source="rss",
                url="https://example.test/older",
                title="older",
                collected_at=now - timedelta(days=1),
            ),
            ContentItem(
                source="rss",
                url="https://example.test/newer",
                title="newer",
                collected_at=now,
            ),
            ContentItem(
                source="web",
                url="https://example.test/middle",
                title="middle",
                collected_at=now - timedelta(hours=1),
            ),
        ]
    )

    page = service.list_articles(limit=2, offset=0)

    assert page.total == 3
    assert [item.title for item in page.items] == ["newer", "middle"]


def test_get_article_returns_detail_by_id():
    service = make_service_with_items(
        [
            ContentItem(
                source="rss",
                url="https://example.test/a",
                title="saved article",
                summary="short",
            )
        ]
    )

    item = service.get_article("rss:https://example.test/a")

    assert item is not None
    assert item.title == "saved article"


def test_list_articles_filters_by_source_tag_and_query():
    now = datetime.now(timezone.utc)
    service = make_service_with_items(
        [
            ContentItem(
                source="rss",
                url="https://example.test/a",
                title="Python release",
                summary="Runtime update",
                tags=["技术发布"],
                collected_at=now,
            ),
            ContentItem(
                source="web",
                url="https://example.test/b",
                title="Hiring backend engineers",
                summary="Jobs update",
                tags=["就业招聘"],
                collected_at=now - timedelta(hours=1),
            ),
            ContentItem(
                source="rss",
                url="https://example.test/c",
                title="Contest calendar",
                summary="Programming contest",
                tags=["比赛信息"],
                collected_at=now - timedelta(hours=2),
            ),
        ]
    )

    page = service.list_articles(source="rss", tag="比赛信息", query="contest")

    assert page.total == 1
    assert [item.title for item in page.items] == ["Contest calendar"]


def test_set_liked_updates_article_and_liked_filter():
    service = make_service_with_items(
        [
            ContentItem(
                source="rss",
                url="https://example.test/a",
                title="keep",
            ),
            ContentItem(
                source="rss",
                url="https://example.test/b",
                title="skip",
            ),
        ]
    )

    assert service.set_liked("rss:https://example.test/a", True) is True

    page = service.list_articles(liked=True)

    assert page.total == 1
    assert [item.title for item in page.items] == ["keep"]


def test_set_liked_returns_false_for_missing_article():
    service = make_service_with_items([])

    assert service.set_liked("missing", True) is False


def test_set_read_state_updates_existing_article_state():
    service = make_service_with_items(
        [
            ContentItem(
                source="rss",
                url="https://example.test/a",
                title="stateful",
            )
        ]
    )

    assert service.set_read_state("rss:https://example.test/a", "ignored") is True
    assert service.get_article_state("rss:https://example.test/a").read_state == "ignored"


def test_set_read_state_rejects_missing_article():
    service = make_service_with_items([])

    assert service.set_read_state("missing", "read") is False


def test_save_note_updates_existing_article_state():
    service = make_service_with_items(
        [
            ContentItem(
                source="rss",
                url="https://example.test/a",
                title="noted",
            )
        ]
    )

    assert service.save_note("rss:https://example.test/a", "Remember this") is True
    assert service.get_article_state("rss:https://example.test/a").user_note == "Remember this"


def test_list_important_unread_excludes_read_and_ignored_articles():
    now = datetime.now(timezone.utc)
    service = make_service_with_items(
        [
            ContentItem(
                source="rss",
                url="https://example.test/unread",
                title="unread important",
                tags=["AI"],
                collected_at=now,
            ),
            ContentItem(
                source="rss",
                url="https://example.test/read",
                title="already read",
                tags=["AI"],
                collected_at=now,
            ),
            ContentItem(
                source="rss",
                url="https://example.test/ignored",
                title="ignored",
                tags=["AI"],
                collected_at=now,
            ),
        ]
    )
    service.set_read_state("rss:https://example.test/read", "read")
    service.set_read_state("rss:https://example.test/ignored", "ignored")

    important = service.list_important_unread()

    assert [entry.article.title for entry in important] == ["unread important"]
    assert important[0].importance_score > 0


def test_list_important_unread_orders_by_score_then_recency():
    now = datetime.now(timezone.utc)
    service = make_service_with_items(
        [
            ContentItem(
                source="rss",
                url="https://example.test/plain-new",
                title="plain new",
                tags=["misc"],
                collected_at=now,
            ),
            ContentItem(
                source="rss",
                url="https://example.test/ai-old",
                title="ai old",
                tags=["AI"],
                collected_at=now - timedelta(days=1),
            ),
            ContentItem(
                source="rss",
                url="https://example.test/liked-old",
                title="liked old",
                tags=["misc"],
                collected_at=now - timedelta(days=2),
            ),
        ]
    )
    service.set_liked("rss:https://example.test/liked-old", True)

    important = service.list_important_unread(limit=3)

    assert [entry.article.title for entry in important] == [
        "liked old",
        "ai old",
        "plain new",
    ]
    assert important[0].importance_score > important[1].importance_score

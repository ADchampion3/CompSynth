from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from comp_synth.schema.content_item import ContentItem
from comp_synth.store.models import ArticleModel, Base
from comp_synth.store.repositories.article_repository import ArticleRepository


def test_update_preserves_user_tags_on_recrawl():
    """Re-crawl should not overwrite user-edited tags."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        repo = ArticleRepository(session)
        repo.save(
            ContentItem(
                source="rss",
                url="https://example.test/a",
                title="old",
                tags=["old-tag"],
                collected_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

        # User edits tags
        repo.update_tags("rss:https://example.test/a", ["user-edited"])
        session.commit()

        # Re-crawl saves updated content but should preserve user tags
        repo.save(
            ContentItem(
                source="rss",
                url="https://example.test/a",
                title="new title",
                tags=["crawl-tag"],
                metadata={"feed_url": "https://example.test/feed.xml"},
                collected_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

        item = repo.get_by_id("rss:https://example.test/a")

    assert item.tags == ["user-edited"]
    assert item.title == "new title"
    assert item.metadata["feed_url"] == "https://example.test/feed.xml"


def test_get_by_id_defaults_legacy_rows_to_other_tag():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        repo = ArticleRepository(session)
        repo.save(
            ContentItem(
                source="rss",
                url="https://example.test/no-tags",
                title="legacy",
                tags=[],
                collected_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

        row = session.get(ArticleModel, "rss:https://example.test/no-tags")
        row.tags = "[]"
        session.commit()

        item = repo.get_by_id("rss:https://example.test/no-tags")

    assert item.tags == ["其他"]


def test_update_tags_modifies_only_tags():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        repo = ArticleRepository(session)
        repo.save(
            ContentItem(
                source="rss",
                url="https://example.test/a",
                title="original",
                tags=["old"],
                collected_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

        repo.update_tags("rss:https://example.test/a", ["new"])
        session.commit()

        item = repo.get_by_id("rss:https://example.test/a")

    assert item.tags == ["new"]
    assert item.title == "original"


def test_update_tags_returns_false_for_missing():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        repo = ArticleRepository(session)
        result = repo.update_tags("nonexistent:id", ["tag"])

    assert result is False


def test_get_tag_vocabulary():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        repo = ArticleRepository(session)
        repo.save(ContentItem(source="rss", url="https://a.com/1", tags=["技术博客", "AI"], collected_at=datetime.now(timezone.utc)))
        repo.save(ContentItem(source="rss", url="https://a.com/2", tags=["AI", "安全"], collected_at=datetime.now(timezone.utc)))
        session.commit()

        vocab = repo.get_tag_vocabulary()

    assert set(vocab) == {"AI", "安全", "技术博客"}


def test_tag_filter_uses_json_each():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        repo = ArticleRepository(session)
        repo.save(ContentItem(source="rss", url="https://a.com/1", tags=["技术博客"], collected_at=datetime.now(timezone.utc)))
        repo.save(ContentItem(source="rss", url="https://a.com/2", tags=["比赛信息"], collected_at=datetime.now(timezone.utc)))
        session.commit()

        results = repo.list_recent(tag="技术博客")

    assert len(results) == 1
    assert results[0].tags == ["技术博客"]

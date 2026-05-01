from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from comp_synth.schema.content_item import ContentItem
from comp_synth.store.models import ArticleModel, Base
from comp_synth.store.repositories.article_repository import ArticleRepository


def test_update_preserves_tags_in_metadata():
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

        repo.save(
            ContentItem(
                source="rss",
                url="https://example.test/a",
                title="new",
                tags=["new-tag"],
                metadata={"feed_url": "https://example.test/feed.xml"},
                collected_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

        item = repo.get_by_id("rss:https://example.test/a")

    assert item.tags == ["new-tag"]
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
        row.extra_metadata = {}
        session.commit()

        item = repo.get_by_id("rss:https://example.test/no-tags")

    assert item.tags == ["其他"]

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from comp_synth.crawlers.adaptive_web_crawler import AdaptiveWebCrawler
from comp_synth.orchestration.content_manager import ContentManager
from comp_synth.schema.content_item import WebPageItem
from comp_synth.store.models import Base
from comp_synth.store.repositories.site_schema_repository import SiteSchemaRepository
from comp_synth.store.repositories.source_crawl_outcome_repository import (
    SourceCrawlOutcomeRepository,
)


def test_source_outcome_counts_distinct_zero_days_and_ignores_errors():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    now = datetime(2026, 4, 30, 10, 0, 0)

    with Session() as session:
        repo = SourceCrawlOutcomeRepository(session)
        repo.record(
            source_key="Tech Blog",
            source_type="web",
            site_name="example.test",
            source_url="https://example.test",
            new_item_count=0,
            error=None,
            crawled_at=now - timedelta(days=2),
        )
        repo.record(
            source_key="Tech Blog",
            source_type="web",
            site_name="example.test",
            source_url="https://example.test",
            new_item_count=0,
            error=None,
            crawled_at=now - timedelta(days=1),
        )
        repo.record(
            source_key="Tech Blog",
            source_type="web",
            site_name="example.test",
            source_url="https://example.test",
            new_item_count=0,
            error="timeout",
            crawled_at=now,
        )
        repo.record(
            source_key="Tech Blog",
            source_type="web",
            site_name="example.test",
            source_url="https://example.test",
            new_item_count=3,
            error=None,
            crawled_at=now,
        )
        session.commit()

        zero_days = repo.count_recent_zero_days(
            "Tech Blog",
            lookback_days=7,
            now=now,
        )
        last_success = repo.last_success_count("Tech Blog")

    assert zero_days == 2
    assert last_success == 3


def test_source_outcome_lists_source_health_by_latest_outcome_and_zero_days():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    now = datetime(2026, 4, 30, 10, 0, 0)

    with Session() as session:
        repo = SourceCrawlOutcomeRepository(session)
        repo.record(
            source_key="Stale Feed",
            source_type="web",
            site_name="stale.test",
            source_url="https://stale.test",
            new_item_count=0,
            error=None,
            crawled_at=now - timedelta(days=2),
        )
        repo.record(
            source_key="Stale Feed",
            source_type="web",
            site_name="stale.test",
            source_url="https://stale.test",
            new_item_count=0,
            error=None,
            crawled_at=now - timedelta(days=1),
        )
        repo.record(
            source_key="Broken Feed",
            source_type="rss",
            site_name="broken.test",
            source_url="https://broken.test/feed.xml",
            new_item_count=0,
            error="timeout",
            crawled_at=now,
        )
        repo.record(
            source_key="Healthy Feed",
            source_type="rss",
            site_name="healthy.test",
            source_url="https://healthy.test/feed.xml",
            new_item_count=4,
            error=None,
            crawled_at=now - timedelta(hours=1),
        )
        session.commit()

        health = repo.list_source_health(
            lookback_days=7,
            zero_day_threshold=2,
            now=now,
        )

    assert [(entry.source_key, entry.status, entry.recent_zero_days, entry.last_error) for entry in health] == [
        ("Broken Feed", "failed", 0, "timeout"),
        ("Stale Feed", "stale", 2, None),
        ("Healthy Feed", "healthy", 0, None),
    ]


def test_site_schema_repository_tracks_stale_refresh_cooldown():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    now = datetime(2026, 4, 30, 10, 0, 0)

    with Session() as session:
        repo = SiteSchemaRepository(session)
        assert repo.can_refresh_stale_selectors(
            "example.test",
            cooldown_hours=24,
            now=now,
        )

        repo.mark_stale_refresh_called("example.test", now=now)
        session.commit()

        assert not repo.can_refresh_stale_selectors(
            "example.test",
            cooldown_hours=24,
            now=now + timedelta(hours=23),
        )
        assert repo.can_refresh_stale_selectors(
            "example.test",
            cooldown_hours=24,
            now=now + timedelta(hours=25),
        )


def test_content_manager_records_source_outcomes(monkeypatch):
    records = []

    class FakeOutcomeStore:
        def record_source_outcome(self, source, count, error):
            records.append((source, count, error))

    class FakeTracker:
        def save_articles(self, items):
            pass

    manager = ContentManager(
        crawl_tracker=FakeTracker(),
        source_outcome_store=FakeOutcomeStore(),
    )

    async def fake_fetch_single_source(source):
        if source["name"] == "Broken":
            return (source["name"], None, "boom")
        return (source["name"], [
            WebPageItem(url="https://good.test/1", title="A"),
            WebPageItem(url="https://good.test/2", title="B"),
        ], None)

    monkeypatch.setattr(manager, "_fetch_single_source", fake_fetch_single_source)

    async def run():
        return await manager.fetch_all([
            {"type": "web", "name": "Good", "url": "https://good.test"},
            {"type": "web", "name": "Broken", "url": "https://broken.test"},
        ])

    result = asyncio.run(run())

    assert result.source_counts == {"Good": 2, "Broken": 0}
    assert records == [
        ({"type": "web", "name": "Good", "url": "https://good.test"}, 2, None),
        ({"type": "web", "name": "Broken", "url": "https://broken.test"}, 0, "boom"),
    ]


def test_stale_cached_selectors_trigger_llm_refresh(monkeypatch):
    crawler = AdaptiveWebCrawler()
    calls = []

    class FakeSchema:
        selectors = [{"item_container": ".old", "url": "a", "title": ".title"}]

    class FakeSchemaStore:
        def get(self, site_name):
            return FakeSchema()

        def can_use_llm(self, site_name):
            return False

        def can_refresh_stale_selectors(self, site_name):
            return True

        def mark_stale_refresh_called(self, site_name):
            calls.append(("mark_stale_refresh_called", site_name))

        def save(self, schema):
            calls.append(("save", schema.selectors))

        def mark_llm_called(self, site_name):
            calls.append(("mark_llm_called", site_name))

    class FakeOutcomeStore:
        def should_refresh_selectors(self, source_key, source_type):
            return True

    class FakeExtractor:
        def extract_list_items_with_selectors(self, html, selectors):
            calls.append(("extract", selectors))
            if selectors[0]["item_container"] == ".old":
                return []
            return [{"url": "/new", "title": "New Article"}]

        async def generate_list_item_selectors(self, html):
            calls.append(("generate", html))
            return [{"item_container": ".new", "url": "a", "title": ".title"}]

    crawler._schema_store = FakeSchemaStore()
    crawler._source_outcome_store = FakeOutcomeStore()
    crawler._dom_extractor = FakeExtractor()

    async def run():
        return await crawler._extract_list_items(
            "<html></html>",
            "https://example.test",
            "example.test",
            source_key="Tech Blog",
            source_type="web",
        )

    items = asyncio.run(run())

    assert items == [{"url": "https://example.test/new", "title": "New Article"}]
    assert ("generate", "<html></html>") in calls
    assert ("extract", [{"item_container": ".old", "url": "a", "title": ".title"}]) not in calls
    assert ("mark_stale_refresh_called", "example.test") in calls


def test_llm_selectors_are_not_saved_when_extraction_is_invalid():
    crawler = AdaptiveWebCrawler()
    calls = []

    class FakeSchemaStore:
        def save(self, schema):
            calls.append(("save", schema.selectors))

        def mark_llm_called(self, site_name):
            calls.append(("mark_llm_called", site_name))

        def mark_stale_refresh_called(self, site_name):
            calls.append(("mark_stale_refresh_called", site_name))

    class FakeExtractor:
        async def generate_list_item_selectors(self, html):
            return [{"item_container": ".bad", "url": "a", "title": ".title"}]

        def extract_list_items_with_selectors(self, html, selectors):
            return [{"url": "", "title": ""}]

    crawler._schema_store = FakeSchemaStore()
    crawler._dom_extractor = FakeExtractor()

    async def run():
        return await crawler._learn_list_item_schema(
            "<html></html>",
            "example.test",
            "https://example.test",
        )

    items = asyncio.run(run())

    assert items == []
    assert ("save", [{"item_container": ".bad", "url": "a", "title": ".title"}]) not in calls
    assert ("mark_llm_called", "example.test") in calls

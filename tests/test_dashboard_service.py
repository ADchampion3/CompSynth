from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from comp_synth.schema.content_item import ContentItem
from comp_synth.services.article_service import ArticleService
from comp_synth.services.dashboard_service import DashboardService
from comp_synth.store.models import Base
from comp_synth.store.repositories.article_repository import ArticleRepository
from comp_synth.store.repositories.article_state_repository import (
    ArticleStateRepository,
)
from comp_synth.store.repositories.crawl_run_repository import CrawlRunRepository
from comp_synth.store.repositories.source_crawl_outcome_repository import (
    SourceCrawlOutcomeRepository,
)


def test_get_summary_returns_article_counts_latest_run_and_failed_sources():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        article_repo = ArticleRepository(session)
        state_repo = ArticleStateRepository(session)
        crawl_repo = CrawlRunRepository(session)
        now = datetime.now(timezone.utc)
        article_repo.save(
            ContentItem(
                source="rss",
                url="https://example.test/important",
                title="Important AI",
                tags=["AI"],
                collected_at=now,
            )
        )
        article_repo.save(
            ContentItem(
                source="rss",
                url="https://example.test/read",
                title="Read AI",
                tags=["AI"],
                collected_at=now - timedelta(hours=1),
            )
        )
        state_repo.set_read_state("rss:https://example.test/read", "read")
        old_run = crawl_repo.start("old-run", "all", now=now - timedelta(days=1))
        crawl_repo.finish(old_run.run_id, "success", new_items=1, now=now - timedelta(days=1, minutes=-1))
        latest_run = crawl_repo.start("latest-run", "all", now=now)
        crawl_repo.finish(latest_run.run_id, "partial", new_items=2, errors=["[Bad Feed] timeout"], now=now)
        crawl_repo.record_source(
            run_id="latest-run",
            source_key="Good Feed",
            source_type="rss",
            source_url="https://example.test/good.xml",
            status="success",
            new_items=2,
        )
        crawl_repo.record_source(
            run_id="latest-run",
            source_key="Bad Feed",
            source_type="rss",
            source_url="https://example.test/bad.xml",
            status="failed",
            error_text="timeout",
        )
        session.commit()

        service = DashboardService(
            article_service=ArticleService(article_repo, state_repo),
            crawl_run_repository=crawl_repo,
        )

        summary = service.get_summary()

    assert summary.article_count == 2
    assert summary.important_unread_count == 1
    assert [entry.article.title for entry in summary.important_unread] == ["Important AI"]
    assert summary.latest_crawl_run is not None
    assert summary.latest_crawl_run.run_id == "latest-run"
    assert summary.latest_crawl_run.status == "partial"
    assert [(source.source_key, source.error_text) for source in summary.failed_sources] == [
        ("Bad Feed", "timeout")
    ]


def test_get_summary_handles_missing_crawl_repository():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        article_repo = ArticleRepository(session)
        article_repo.save(ContentItem(source="rss", url="https://example.test/a", title="A"))
        session.commit()

        service = DashboardService(article_service=ArticleService(article_repo))

        summary = service.get_summary()

    assert summary.article_count == 1
    assert summary.latest_crawl_run is None
    assert summary.failed_sources == []


def test_get_summary_includes_unhealthy_source_history():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        article_repo = ArticleRepository(session)
        outcome_repo = SourceCrawlOutcomeRepository(session)
        now = datetime(2026, 4, 30, 10, 0, 0)
        outcome_repo.record(
            source_key="Stale Feed",
            source_type="web",
            site_name="stale.test",
            source_url="https://stale.test",
            new_item_count=0,
            error=None,
            crawled_at=now - timedelta(days=2),
        )
        outcome_repo.record(
            source_key="Stale Feed",
            source_type="web",
            site_name="stale.test",
            source_url="https://stale.test",
            new_item_count=0,
            error=None,
            crawled_at=now - timedelta(days=1),
        )
        outcome_repo.record(
            source_key="Healthy Feed",
            source_type="rss",
            site_name="healthy.test",
            source_url="https://healthy.test/feed.xml",
            new_item_count=3,
            error=None,
            crawled_at=now,
        )
        outcome_repo.record(
            source_key="Broken Feed",
            source_type="rss",
            site_name="broken.test",
            source_url="https://broken.test/feed.xml",
            new_item_count=0,
            error="timeout",
            crawled_at=now,
        )
        session.commit()

        service = DashboardService(
            article_service=ArticleService(article_repo),
            source_outcome_repository=outcome_repo,
        )

        summary = service.get_summary(source_health_lookback_days=7, source_zero_day_threshold=2)

    assert [(entry.source_key, entry.status) for entry in summary.unhealthy_sources] == [
        ("Broken Feed", "failed"),
        ("Stale Feed", "stale"),
    ]


def test_get_summary_includes_stale_running_crawl_runs():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    now = datetime(2026, 4, 30, 10, 0, 0, tzinfo=timezone.utc)

    with Session() as session:
        article_repo = ArticleRepository(session)
        crawl_repo = CrawlRunRepository(session)
        crawl_repo.start("stuck-run", "all", now=now - timedelta(hours=2))
        crawl_repo.start("active-run", "all", now=now - timedelta(minutes=5))
        session.commit()

        service = DashboardService(
            article_service=ArticleService(article_repo),
            crawl_run_repository=crawl_repo,
        )

        summary = service.get_summary(stale_run_after_minutes=60, now=now)

    assert [run.run_id for run in summary.stale_running_runs] == ["stuck-run"]

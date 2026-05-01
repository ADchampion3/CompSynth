import asyncio
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from comp_synth.services.crawl_service import CrawlService
from comp_synth.store.models import Base
from comp_synth.store.repositories.crawl_run_repository import CrawlRunRepository


def test_run_all_delegates_to_pipeline_runner_with_initial_state():
    calls = []

    async def fake_runner(initial_state=None):
        calls.append(initial_state)
        return {
            "errors": [],
            "publish_results": {"status": "success", "path": "digest.md"},
        }

    service = CrawlService(pipeline_runner=fake_runner)

    result = asyncio.run(service.run_all({"errors": ["seed"]}))

    assert calls == [{"errors": ["seed"]}]
    assert result["publish_results"]["path"] == "digest.md"


def test_run_all_defaults_to_empty_initial_state():
    calls = []

    async def fake_runner(initial_state=None):
        calls.append(initial_state)
        return {"errors": [], "publish_results": {"status": "skipped"}}

    service = CrawlService(pipeline_runner=fake_runner)

    result = asyncio.run(service.run_all())

    assert calls == [None]
    assert result["publish_results"]["status"] == "skipped"


def test_run_all_records_successful_crawl_run(tmp_path):
    async def fake_runner(initial_state=None):
        return {
            "errors": [],
            "fetched_items": [{"id": "rss:https://example.test/a"}],
            "publish_results": {"status": "success", "path": "digest.md"},
        }

    service = CrawlService(pipeline_runner=fake_runner, crawl_db_path=tmp_path / "crawl_state.db")

    result = asyncio.run(service.run_all())
    run = service.get_run(result["crawl_run_id"])

    assert run is not None
    assert run.run_id == result["crawl_run_id"]
    assert run.scope == "all"
    assert run.status == "success"
    assert run.new_items == 1
    assert run.errors == []
    assert run.started_at is not None
    assert run.finished_at is not None


def test_run_all_records_failed_crawl_run(tmp_path):
    async def fake_runner(initial_state=None):
        raise RuntimeError("crawler exploded")

    service = CrawlService(pipeline_runner=fake_runner, crawl_db_path=tmp_path / "crawl_state.db")

    try:
        asyncio.run(service.run_all())
    except RuntimeError:
        pass

    runs = service.list_runs()
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert runs[0].error_text == "crawler exploded"
    assert runs[0].finished_at is not None


def test_run_all_records_per_source_child_runs(tmp_path):
    async def fake_runner(initial_state=None):
        return {
            "sources": [
                {"type": "rss", "name": "Good Feed", "url": "https://example.test/good.xml"},
                {"type": "web", "url": "https://example.test/bad"},
            ],
            "source_counts": {
                "Good Feed": 3,
                "https://example.test/bad": 0,
            },
            "errors": ["[https://example.test/bad] timeout"],
            "fetched_items": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        }

    service = CrawlService(pipeline_runner=fake_runner, crawl_db_path=tmp_path / "crawl_state.db")

    result = asyncio.run(service.run_all())
    source_runs = service.list_source_runs(result["crawl_run_id"])

    assert [(run.source_key, run.source_type, run.status, run.new_items, run.error_text) for run in source_runs] == [
        ("Good Feed", "rss", "success", 3, None),
        ("https://example.test/bad", "web", "failed", 0, "timeout"),
    ]


def test_crawl_run_repository_lists_stale_running_runs():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    now = datetime(2026, 4, 30, 10, 0, 0)

    with Session() as session:
        repo = CrawlRunRepository(session)
        stale = repo.start("stale-run", "all", now=now - timedelta(hours=2))
        active = repo.start("active-run", "all", now=now - timedelta(minutes=10))
        finished = repo.start("finished-run", "all", now=now - timedelta(hours=3))
        repo.finish(finished.run_id, "success", now=now - timedelta(hours=2, minutes=50))
        session.commit()

        runs = repo.list_stale_running(stale_after_minutes=60, now=now)

    assert [run.run_id for run in runs] == [stale.run_id]
    assert active.run_id not in [run.run_id for run in runs]

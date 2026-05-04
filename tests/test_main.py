import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import comp_synth.main as main_module
from comp_synth.schema.content_item import ContentItem
from comp_synth.store.migrations import bootstrap_database
from comp_synth.store.repositories.article_repository import ArticleRepository
from comp_synth.store.repositories.crawl_run_repository import CrawlRunRepository
from comp_synth.store.repositories.source_crawl_outcome_repository import (
    SourceCrawlOutcomeRepository,
)


def test_run_uses_crawl_service(monkeypatch):
    calls = []

    class FakeCrawlService:
        def __init__(self, crawl_db_path=None):
            calls.append(("init", crawl_db_path))

        async def run_all(self):
            calls.append(("run_all", None))
            return {
                "errors": [],
                "publish_results": {"status": "success", "path": "digest.md"},
            }

    monkeypatch.setattr(main_module, "CrawlService", FakeCrawlService)

    result = asyncio.run(main_module.run())

    assert calls == [("init", None), ("run_all", None)]
    assert result["publish_results"]["path"] == "digest.md"


def test_main_passes_db_path_to_crawl_service(monkeypatch, tmp_path):
    calls = []
    db_path = tmp_path / "crawl_state.db"

    class FakeCrawlService:
        def __init__(self, crawl_db_path=None):
            calls.append(("init", crawl_db_path))

        async def run_all(self):
            calls.append(("run_all", None))
            return {"errors": [], "publish_results": {"status": "skipped"}}

    monkeypatch.setattr(main_module, "CrawlService", FakeCrawlService)

    main_module.main(["--db-path", str(db_path)])

    assert calls == [("init", db_path), ("run_all", None)]


def test_crawl_command_prints_run_summary_json(monkeypatch, tmp_path, capsys):
    calls = []
    db_path = tmp_path / "crawl_state.db"

    class FakeCrawlService:
        def __init__(self, crawl_db_path=None):
            calls.append(("init", crawl_db_path))

        async def run_all(self):
            calls.append(("run_all", None))
            return {
                "crawl_run_id": "run-123",
                "errors": ["[Bad Feed] timeout"],
                "fetched_items": [{"id": "a"}, {"id": "b"}],
                "publish_results": {"status": "success", "path": "digest.md"},
            }

    monkeypatch.setattr(main_module, "CrawlService", FakeCrawlService)

    main_module.main(["--db-path", str(db_path), "crawl"])

    payload = json.loads(capsys.readouterr().out)
    assert calls == [("init", db_path), ("run_all", None)]
    assert payload == {
        "crawl_run_id": "run-123",
        "status": "success",
        "new_items": 2,
        "errors": ["[Bad Feed] timeout"],
        "publish_path": "digest.md",
    }


def test_dashboard_command_prints_summary_json(tmp_path, capsys):
    db_path = tmp_path / "crawl_state.db"
    engine = create_engine(f"sqlite:///{db_path}")
    bootstrap_database(engine)
    Session = sessionmaker(bind=engine)
    now = datetime.now(timezone.utc)

    with Session() as session:
        article_repo = ArticleRepository(session)
        crawl_repo = CrawlRunRepository(session)
        outcome_repo = SourceCrawlOutcomeRepository(session)
        article_repo.save(
            ContentItem(
                source="rss",
                url="https://example.test/a",
                title="Important AI",
                tags=["AI"],
                collected_at=now,
            )
        )
        stale_run = crawl_repo.start("stale-run", "all", now=now - timedelta(hours=2))
        run = crawl_repo.start("run-1", "all", now=now)
        crawl_repo.finish(run.run_id, "success", new_items=1, now=now)
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

    main_module.main(["--db-path", str(db_path), "dashboard"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["article_count"] == 1
    assert payload["important_unread_count"] == 1
    assert payload["latest_crawl_run"]["run_id"] == "run-1"
    assert payload["latest_crawl_run"]["status"] == "success"
    assert payload["stale_running_runs"] == [
        {
            "run_id": "stale-run",
            "scope": "all",
            "status": "running",
            "new_items": 0,
            "started_at": stale_run.started_at.isoformat(),
            "finished_at": None,
            "errors": [],
            "error_text": None,
        }
    ]
    assert payload["unhealthy_sources"] == [
        {
            "source_key": "Broken Feed",
            "source_type": "rss",
            "source_url": "https://broken.test/feed.xml",
            "status": "failed",
            "recent_zero_days": 0,
            "last_error": "timeout",
        }
    ]


def test_sources_import_command_persists_yaml_to_database(tmp_path, capsys):
    db_path = tmp_path / "crawl_state.db"
    subscriptions = tmp_path / "subscriptions.yaml"
    subscriptions.write_text(
        """
sources:
  - type: rss
    name: Example Feed
    url: https://example.test/feed.xml
""",
        encoding="utf-8",
    )

    main_module.main(["--db-path", str(db_path), "sources", "import", "--path", str(subscriptions)])

    payload = json.loads(capsys.readouterr().out)
    assert payload == {"imported": 1}

    service = main_module.SourceService(source_db_path=db_path)
    sources = service.list_sources()
    assert [source.source_key for source in sources] == ["https://example.test/feed.xml"]


def test_sources_export_command_writes_yaml_from_database(tmp_path, capsys):
    db_path = tmp_path / "crawl_state.db"
    subscriptions = tmp_path / "subscriptions.yaml"
    subscriptions.write_text(
        """
sources:
  - type: web
    name: Example Site
    url: https://example.test/
    enabled: false
""",
        encoding="utf-8",
    )
    exported = tmp_path / "exported.yaml"
    main_module.SourceService(subscriptions_path=subscriptions, source_db_path=db_path).import_yaml()

    main_module.main(["--db-path", str(db_path), "sources", "export", "--output", str(exported)])

    payload = json.loads(capsys.readouterr().out)
    assert payload == {"exported": str(exported)}
    reloaded = main_module.SourceService(subscriptions_path=exported)
    sources = reloaded.list_sources()
    assert [source.source_key for source in sources] == ["https://example.test/"]
    assert sources[0].enabled is False


def test_reports_list_command_prints_report_metadata_json(tmp_path, capsys):
    db_path = tmp_path / "crawl_state.db"
    report_path = tmp_path / "reports" / "digest.md"
    report_path.parent.mkdir()
    report_path.write_text("# Daily Intelligence\n", encoding="utf-8")
    main_module.ReportService(output_dir=tmp_path, report_db_path=db_path).record_report(
        report_id="digest_20260201",
        title="Daily Intelligence",
        markdown_path=report_path,
    )

    main_module.main(["--db-path", str(db_path), "reports", "list"])

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "reports": [
            {
                "report_id": "digest_20260201",
                "title": "Daily Intelligence",
                "path": str(report_path),
            }
        ]
    }


def test_reports_get_command_prints_report_markdown_json(tmp_path, capsys):
    db_path = tmp_path / "crawl_state.db"
    report_path = tmp_path / "reports" / "digest.md"
    report_path.parent.mkdir()
    report_path.write_text("# Daily Intelligence\nBody", encoding="utf-8")
    main_module.ReportService(output_dir=tmp_path, report_db_path=db_path).record_report(
        report_id="digest_20260201",
        title="Daily Intelligence",
        markdown_path=report_path,
    )

    main_module.main(["--db-path", str(db_path), "reports", "get", "digest_20260201"])

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "report_id": "digest_20260201",
        "title": "Daily Intelligence",
        "path": str(report_path),
        "markdown": "# Daily Intelligence\nBody",
    }

"""API endpoint tests using FastAPI TestClient with in-memory SQLite."""

import tempfile
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from comp_synth.api.app import create_app
from comp_synth.api.deps import (
    get_crawl_service,
    get_report_service,
    get_session,
    get_source_service,
)
from comp_synth.api.routers.tags import invalidate_tag_cache
from comp_synth.schema.content_item import ContentItem
from comp_synth.services.crawl_service import CrawlService
from comp_synth.services.report_service import ReportService
from comp_synth.services.source_service import SourceService
from comp_synth.store.migrations import bootstrap_database
from comp_synth.store.repositories.article_repository import ArticleRepository


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    bootstrap_database(engine)
    return engine


@pytest.fixture(autouse=True)
def _reset_tag_cache():
    invalidate_tag_cache()
    yield
    invalidate_tag_cache()


def _make_session(engine) -> Session:
    return sessionmaker(bind=engine)()


def _seed_articles(session: Session, items: list[ContentItem]) -> None:
    repo = ArticleRepository(session)
    for item in items:
        repo.save(item)
    session.commit()


def _sample_items(now: datetime | None = None) -> list[ContentItem]:
    now = now or datetime.now(timezone.utc)
    return [
        ContentItem(
            source="rss",
            url="https://example.test/1",
            title="First article",
            summary="Summary one",
            tags=["技术博客"],
            collected_at=now,
        ),
        ContentItem(
            source="web",
            url="https://example.test/2",
            title="Second article",
            summary="Summary two",
            tags=["其他"],
            collected_at=now - timedelta(hours=1),
        ),
    ]


@pytest.fixture()
def output_dir():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "output"
        out.mkdir()
        yield out


@pytest.fixture()
def subscriptions_yaml():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "subscriptions.yaml"
        path.write_text(
            "sources:\n"
            "  - type: rss\n"
            "    url: https://example.test/feed\n"
            "    name: test-source\n",
            encoding="utf-8",
        )
        yield path


def _override_session(app, engine) -> None:
    """Override get_session to yield sessions from the test engine."""
    def _test_session() -> Generator[Session, None, None]:
        session = sessionmaker(bind=engine)()
        try:
            yield session
        finally:
            session.close()
    app.dependency_overrides[get_session] = _test_session


def _make_test_client(
    output_dir: Path,
    subscriptions_path: Path | None = None,
    crawl_service: CrawlService | None = None,
    db_path: Path | None = None,
    engine=None,
) -> TestClient:
    engine = engine or _make_engine()
    app = create_app()
    _override_session(app, engine)

    source_svc = SourceService(
        subscriptions_path=subscriptions_path or Path("nonexistent.yaml"),
        source_db_path=db_path,
    )
    report_svc = ReportService(output_dir=output_dir, report_db_path=db_path)
    crawl_svc = crawl_service or CrawlService(crawl_db_path=db_path)

    app.dependency_overrides[get_source_service] = lambda: source_svc
    app.dependency_overrides[get_report_service] = lambda: report_svc
    app.dependency_overrides[get_crawl_service] = lambda: crawl_svc

    return TestClient(app)


def _make_app_with_articles(
    output_dir: Path,
    items: list[ContentItem],
) -> tuple[TestClient, list[ContentItem]]:
    engine = _make_engine()
    session = _make_session(engine)
    _seed_articles(session, items)

    app = create_app()
    _override_session(app, engine)
    return TestClient(app), items


# --- Articles ---


class TestArticlesAPI:
    def test_list_articles_empty(self, output_dir):
        client = _make_test_client(output_dir)
        resp = client.get("/api/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_articles_with_items(self, output_dir):
        client, items = _make_app_with_articles(output_dir, _sample_items())
        resp = client.get("/api/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["items"][0]["title"] == "First article"

    def test_list_articles_filtered_by_source(self, output_dir):
        client, _ = _make_app_with_articles(output_dir, _sample_items())
        resp = client.get("/api/articles", params={"source": "rss"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["source"] == "rss"

    def test_get_article_found(self, output_dir):
        client, items = _make_app_with_articles(output_dir, _sample_items())
        resp = client.get("/api/articles/detail", params={"article_id": items[0].id})
        assert resp.status_code == 200
        assert resp.json()["title"] == "First article"

    def test_get_article_missing(self, output_dir):
        client = _make_test_client(output_dir)
        resp = client.get("/api/articles/detail", params={"article_id": "nonexistent:id"})
        assert resp.status_code == 404

    def test_update_article_state(self, output_dir):
        client, items = _make_app_with_articles(output_dir, _sample_items())
        resp = client.patch(
            "/api/articles/state",
            params={"article_id": items[0].id},
            json={"read_state": "read"},
        )
        assert resp.status_code == 200
        assert resp.json()["read_state"] == "read"

    def test_update_article_like(self, output_dir):
        client, items = _make_app_with_articles(output_dir, _sample_items())
        resp = client.patch(
            "/api/articles/like",
            params={"article_id": items[0].id},
            json={"liked": True},
        )
        assert resp.status_code == 200

    def test_update_article_note(self, output_dir):
        client, items = _make_app_with_articles(output_dir, _sample_items())
        resp = client.patch(
            "/api/articles/note",
            params={"article_id": items[0].id},
            json={"user_note": "Interesting read"},
        )
        assert resp.status_code == 200
        assert resp.json()["user_note"] == "Interesting read"

    def test_get_article_state(self, output_dir):
        client, items = _make_app_with_articles(output_dir, _sample_items())
        resp = client.get("/api/articles/state", params={"article_id": items[0].id})
        assert resp.status_code == 200
        assert resp.json()["read_state"] == "unread"

    def test_get_related_placeholder(self, output_dir):
        client = _make_test_client(output_dir)
        resp = client.get("/api/articles/related", params={"article_id": "some:id"})
        assert resp.status_code == 200
        assert resp.json()["implemented"] is False

    def test_list_articles_filtered_by_tag(self, output_dir):
        client, _ = _make_app_with_articles(output_dir, _sample_items())
        resp = client.get("/api/articles", params={"tag": "技术博客"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "First article"

    def test_list_articles_filtered_by_nonexistent_tag(self, output_dir):
        client, _ = _make_app_with_articles(output_dir, _sample_items())
        resp = client.get("/api/articles", params={"tag": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestTagsAPI:
    def test_get_tags_empty(self, output_dir):
        client = _make_test_client(output_dir)
        resp = client.get("/api/tags")
        assert resp.status_code == 200
        assert resp.json()["tags"] == []

    def test_get_tags_returns_distinct(self, output_dir):
        client, _ = _make_app_with_articles(output_dir, _sample_items())
        resp = client.get("/api/tags")
        assert resp.status_code == 200
        tags = resp.json()["tags"]
        assert "技术博客" in tags
        assert "其他" in tags

    def test_update_article_tags(self, output_dir):
        client, items = _make_app_with_articles(output_dir, _sample_items())
        resp = client.patch(
            "/api/articles/tags",
            params={"article_id": items[0].id},
            json={"tags": ["技术博客", "new-tag"]},
        )
        assert resp.status_code == 200
        assert "new-tag" in resp.json()["tags"]

    def test_update_article_tags_clear(self, output_dir):
        client, items = _make_app_with_articles(output_dir, _sample_items())
        resp = client.patch(
            "/api/articles/tags",
            params={"article_id": items[0].id},
            json={"tags": []},
        )
        assert resp.status_code == 200
        # Empty tags are returned as ["其他"] by _parse_tags
        assert resp.json()["tags"] == ["其他"]

    def test_update_tags_nonexistent_article(self, output_dir):
        client = _make_test_client(output_dir)
        resp = client.patch(
            "/api/articles/tags",
            params={"article_id": "nonexistent:id"},
            json={"tags": ["test"]},
        )
        assert resp.status_code == 404

    def test_update_tags_rejects_too_long(self, output_dir):
        client, items = _make_app_with_articles(output_dir, _sample_items())
        resp = client.patch(
            "/api/articles/tags",
            params={"article_id": items[0].id},
            json={"tags": ["a" * 51]},
        )
        assert resp.status_code == 422

    def test_update_tags_rejects_control_chars(self, output_dir):
        client, items = _make_app_with_articles(output_dir, _sample_items())
        resp = client.patch(
            "/api/articles/tags",
            params={"article_id": items[0].id},
            json={"tags": ["tag\nwith\nnewlines"]},
        )
        assert resp.status_code == 422

    def test_update_tags_deduplicates(self, output_dir):
        client, items = _make_app_with_articles(output_dir, _sample_items())
        resp = client.patch(
            "/api/articles/tags",
            params={"article_id": items[0].id},
            json={"tags": ["技术博客", "技术博客"]},
        )
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["技术博客"]


# --- Sources ---


class TestSourcesAPI:
    def test_list_sources_from_yaml(self, output_dir, subscriptions_yaml, tmp_path):
        db = tmp_path / "test.db"
        client = _make_test_client(output_dir, subscriptions_yaml, db_path=db)
        resp = client.get("/api/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["source_key"] == "test-source"

    def test_import_yaml(self, output_dir, subscriptions_yaml, tmp_path):
        db = tmp_path / "test.db"
        client = _make_test_client(output_dir, subscriptions_yaml, db_path=db)
        resp = client.post("/api/sources/import-yaml")
        assert resp.status_code == 200
        assert resp.json()["imported"] >= 1

    def test_export_yaml(self, output_dir, subscriptions_yaml, tmp_path):
        db = tmp_path / "test.db"
        client = _make_test_client(output_dir, subscriptions_yaml, db_path=db)
        client.post("/api/sources/import-yaml")
        export_resp = client.get("/api/sources/export-yaml")
        assert export_resp.status_code == 200
        assert "sources:" in export_resp.text


# --- Crawls ---


class TestCrawlsAPI:
    def test_list_crawls_empty(self, output_dir, tmp_path):
        db = tmp_path / "test.db"
        client = _make_test_client(output_dir, db_path=db)
        resp = client.get("/api/crawls")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_start_crawl(self, output_dir, tmp_path):
        db = tmp_path / "test.db"
        client = _make_test_client(output_dir, db_path=db)
        with patch.object(CrawlService, "run_all", new_callable=AsyncMock, return_value={"errors": []}):
            resp = client.post("/api/crawls")
            assert resp.status_code == 200
            assert resp.json()["status"] == "started"

    def test_get_crawl_run_not_found(self, output_dir, tmp_path):
        db = tmp_path / "test.db"
        client = _make_test_client(output_dir, db_path=db)
        resp = client.get("/api/crawls/nonexistent")
        assert resp.status_code == 404


# --- Reports ---


class TestReportsAPI:
    def test_list_reports_empty(self, output_dir):
        client = _make_test_client(output_dir)
        resp = client.get("/api/reports")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_report_with_markdown(self, output_dir):
        (output_dir / "digest_20260501.md").write_text("# Test Report\nHello", encoding="utf-8")
        client = _make_test_client(output_dir)
        resp = client.get("/api/reports/digest_20260501")
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_id"] == "digest_20260501"
        assert "Hello" in data["markdown"]

    def test_get_report_missing_markdown(self, output_dir):
        client = _make_test_client(output_dir)
        resp = client.get("/api/reports/digest_20991231")
        assert resp.status_code == 404

    def test_get_report_invalid_id(self, output_dir):
        client = _make_test_client(output_dir)
        resp = client.get("/api/reports/invalid")
        assert resp.status_code == 400


# --- Dashboard ---


class TestDashboardAPI:
    def test_dashboard_no_data(self, output_dir):
        engine = _make_engine()
        app = create_app()
        _override_session(app, engine)
        client = TestClient(app)

        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["article_count"] == 0
        assert data["important_unread_count"] == 0
        assert data["latest_crawl_run"] is None

    def test_dashboard_with_data(self, output_dir):
        engine = _make_engine()
        session = _make_session(engine)
        _seed_articles(session, _sample_items())

        app = create_app()
        _override_session(app, engine)
        client = TestClient(app)

        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["article_count"] == 2
        assert data["important_unread_count"] >= 0

"""FastAPI dependency providers for CompSynth services."""

from collections.abc import Generator
from pathlib import Path

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from comp_synth.config import Settings, settings
from comp_synth.services.article_service import ArticleService
from comp_synth.services.crawl_service import CrawlService
from comp_synth.services.dashboard_service import DashboardService
from comp_synth.services.report_service import ReportService
from comp_synth.services.settings_service import SettingsService
from comp_synth.services.source_service import SourceService
from comp_synth.store.migrations import bootstrap_database
from comp_synth.store.models import resolve_db_path
from comp_synth.store.repositories.article_repository import ArticleRepository
from comp_synth.store.repositories.article_state_repository import (
    ArticleStateRepository,
)
from comp_synth.store.repositories.crawl_run_repository import CrawlRunRepository
from comp_synth.store.repositories.settings_repository import SettingsRepository
from comp_synth.store.repositories.source_crawl_outcome_repository import (
    SourceCrawlOutcomeRepository,
)
from comp_synth.store.schema_store import SchemaStore

_engine = None
_session_factory: sessionmaker | None = None


def create_session_factory(db_path: Path | None = None, s: Settings | None = None) -> sessionmaker:
    """Create a session factory for the given or default crawl database path."""
    resolved = resolve_db_path(
        Path(db_path) if db_path else (s or settings).crawl_db_path,
        "crawl_state.db",
    )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{resolved}", echo=False)
    bootstrap_database(engine)
    return sessionmaker(bind=engine)


def _init_db(s: Settings) -> sessionmaker:
    global _engine, _session_factory
    if _session_factory is not None:
        return _session_factory
    resolved = resolve_db_path(s.crawl_db_path, "crawl_state.db")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{resolved}", echo=False)
    bootstrap_database(_engine)
    _session_factory = sessionmaker(bind=_engine)
    return _session_factory


def get_settings() -> Settings:
    return settings


def get_session() -> Generator[Session, None, None]:
    factory = _init_db(get_settings())
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_article_service(session: Session = Depends(get_session)) -> ArticleService:
    return ArticleService(
        repository=ArticleRepository(session),
        state_repository=ArticleStateRepository(session),
    )


def get_source_service() -> SourceService:
    s = get_settings()
    return SourceService(
        subscriptions_path=s.subscriptions_path,
        source_db_path=s.crawl_db_path,
    )


def get_crawl_service() -> CrawlService:
    s = get_settings()
    return CrawlService(crawl_db_path=s.crawl_db_path)


def get_report_service() -> ReportService:
    s = get_settings()
    return ReportService(
        output_dir=s.output_dir,
        report_db_path=s.crawl_db_path,
    )


def get_dashboard_service(session: Session = Depends(get_session)) -> DashboardService:
    article_repo = ArticleRepository(session)
    article_service = ArticleService(article_repo, ArticleStateRepository(session))
    return DashboardService(
        article_service=article_service,
        crawl_run_repository=CrawlRunRepository(session),
        source_outcome_repository=SourceCrawlOutcomeRepository(session),
    )


def get_settings_service(session: Session = Depends(get_session)) -> SettingsService:
    return SettingsService(repository=SettingsRepository(session))


_schema_store: SchemaStore | None = None


def get_schema_store() -> SchemaStore:
    global _schema_store
    if _schema_store is None:
        _schema_store = SchemaStore()
    return _schema_store

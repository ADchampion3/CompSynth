"""FastAPI application factory for CompSynth."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from comp_synth.api.routers import (
    articles,
    crawls,
    dashboard,
    reports,
    settings,
    sources,
    tags,
)
from comp_synth.api.schemas import ErrorDetail


@asynccontextmanager
async def lifespan(app: FastAPI):
    from comp_synth.api.deps import _init_db, get_settings
    from comp_synth.services.source_service import SourceService

    settings = get_settings()
    _init_db(settings)

    # 启动时以 YAML 为准，全量同步到 DB
    try:
        svc = SourceService(
            subscriptions_path=settings.subscriptions_path,
            source_db_path=settings.crawl_db_path,
        )
        svc.import_yaml()
    except Exception as exc:
        from loguru import logger
        logger.warning("启动时 YAML → DB 同步失败: {error}", error=exc)

    # 启动时将中断的 crawl 记录标记为失败
    try:
        from comp_synth.store.database import get_engine
        from comp_synth.store.repositories.crawl_run_repository import (
            CrawlRunRepository,
        )

        _, factory = get_engine(settings.crawl_db_path, "crawl_state.db")
        with factory() as session:
            repo = CrawlRunRepository(session)
            count = repo.mark_running_as_failed()
            session.commit()
            if count > 0:
                from loguru import logger
                logger.info("已将 {count} 条中断的 crawl 记录标记为失败", count=count)
    except Exception as exc:
        from loguru import logger
        logger.warning("清理中断 crawl 记录失败: {error}", error=exc)

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="CompSynth",
        description="Content aggregation and publishing system API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(OperationalError)
    async def database_error_handler(request: Request, exc: OperationalError):
        return JSONResponse(
            status_code=503,
            content=ErrorDetail(
                problem="Database error",
                cause="The local database is unavailable or corrupted.",
                fix="Check that the data directory exists and is writable.",
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=ErrorDetail(
                problem="Internal error",
                cause="An unexpected error occurred.",
                fix="Check the server logs for details.",
            ).model_dump(),
        )

    app.include_router(articles.router, prefix="/api")
    app.include_router(sources.router, prefix="/api")
    app.include_router(crawls.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(tags.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")

    return app

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
    session_factory = _init_db(settings)

    # Apply DB-backed settings overrides before consumers read
    try:
        from comp_synth.config import apply_db_overrides
        from comp_synth.store.repositories.settings_repository import SettingsRepository

        with session_factory() as session:
            repo = SettingsRepository(session)
            overrides = repo.load()
            if overrides:
                apply_db_overrides(overrides)

        # Rebuild LLM registry with overridden settings
        import comp_synth.llm_provider.registry as _reg
        from comp_synth.config import settings as _s
        from comp_synth.llm_provider.registry import LLMRegistry

        _reg.llm_registry = LLMRegistry(_s.model_dump())
    except Exception as exc:
        from loguru import logger

        logger.warning("Settings DB override failed: {error}", error=exc)

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

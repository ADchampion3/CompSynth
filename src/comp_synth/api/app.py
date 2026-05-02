"""FastAPI application factory for CompSynth."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from comp_synth.api.routers import articles, crawls, dashboard, reports, sources, tags
from comp_synth.api.schemas import ErrorDetail


@asynccontextmanager
async def lifespan(app: FastAPI):
    from comp_synth.api.deps import _init_db, get_settings

    _init_db(get_settings())
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

    return app

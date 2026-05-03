"""Sources API router."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from comp_synth.api.deps import get_session, get_source_service
from comp_synth.api.schemas import (
    ErrorDetail,
    SourceCreateRequest,
    SourceResponse,
    SourceUpdateRequest,
)
from comp_synth.services.source_service import SourceService
from comp_synth.store.repositories.source_crawl_outcome_repository import (
    SourceCrawlOutcomeRepository,
)

router = APIRouter(tags=["sources"])


def _source_to_response(source, health=None) -> SourceResponse:
    data = dict(
        source_key=source.source_key,
        source_type=source.source_type,
        url=source.url,
        name=source.name,
        enabled=source.enabled,
        selectors=source.selectors,
        javascript=source.javascript,
    )
    if health is not None:
        data["crawl_status"] = health.status
        data["last_crawled_at"] = health.last_crawled_at
        data["last_new_item_count"] = health.last_new_item_count
        data["recent_zero_days"] = health.recent_zero_days
        data["last_error"] = health.last_error
    return SourceResponse(**data)


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(
    service: SourceService = Depends(get_source_service),
    session: Session = Depends(get_session),
):
    sources = service.list_sources()
    outcome_repo = SourceCrawlOutcomeRepository(session)
    health_by_key = {
        h.source_key: h
        for h in outcome_repo.list_source_health(lookback_days=7, zero_day_threshold=3)
    }
    result = []
    for s in sources:
        health = health_by_key.get(s.source_key)
        result.append(_source_to_response(s, health=health))
    return result


def _sync_yaml(service: SourceService) -> None:
    """Sync database sources to subscriptions.yaml."""
    try:
        service.export_yaml()
    except ValueError as exc:
        from loguru import logger
        logger.debug("YAML sync skipped (no DB configured): {error}", error=exc)
    except Exception as exc:
        from loguru import logger
        logger.warning("YAML sync failed: {error}", error=exc)


@router.post("/sources", response_model=SourceResponse, status_code=201)
def create_source(body: SourceCreateRequest, service: SourceService = Depends(get_source_service)):
    try:
        source = service.create_source(
            source_type=body.source_type,
            url=body.url,
            name=body.name,
            enabled=body.enabled,
            javascript=body.javascript,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _sync_yaml(service)
    return _source_to_response(source)


@router.put("/sources/{source_key}", response_model=SourceResponse)
def update_source(
    source_key: str,
    body: SourceUpdateRequest,
    service: SourceService = Depends(get_source_service),
):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    source = service.update_source(source_key, **fields)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    _sync_yaml(service)
    return _source_to_response(source)


@router.delete("/sources/{source_key}", status_code=204)
def delete_source(source_key: str, service: SourceService = Depends(get_source_service)):
    ok = service.delete_source(source_key)
    if not ok:
        raise HTTPException(status_code=404, detail="Source not found")
    _sync_yaml(service)


@router.post("/sources/import-yaml")
def import_yaml(service: SourceService = Depends(get_source_service)):
    try:
        imported = service.import_yaml()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=ErrorDetail(
                problem="YAML import failed",
                cause=str(exc),
                fix="Check that subscriptions.yaml exists and is valid.",
            ).model_dump(),
        )
    _sync_yaml(service)
    return {"imported": len(imported)}


@router.get("/sources/export-yaml", response_class=PlainTextResponse)
def export_yaml(service: SourceService = Depends(get_source_service)):
    try:
        path = service.export_yaml()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=ErrorDetail(
                problem="YAML export failed",
                cause=str(exc),
                fix="Ensure the source database is configured.",
            ).model_dump(),
        )
    return path.read_text(encoding="utf-8")

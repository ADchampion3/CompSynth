"""Sources API router."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from comp_synth.api.deps import get_source_service
from comp_synth.api.schemas import (
    ErrorDetail,
    SourceCreateRequest,
    SourceResponse,
    SourceUpdateRequest,
)
from comp_synth.services.source_service import SourceService

router = APIRouter(tags=["sources"])


def _source_to_response(source) -> SourceResponse:
    return SourceResponse(
        source_key=source.source_key,
        source_type=source.source_type,
        url=source.url,
        name=source.name,
        enabled=source.enabled,
        selectors=source.selectors,
        javascript=source.javascript,
    )


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(service: SourceService = Depends(get_source_service)):
    sources = service.list_sources()
    return [_source_to_response(s) for s in sources]


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
    return _source_to_response(source)


@router.delete("/sources/{source_key}", status_code=204)
def delete_source(source_key: str, service: SourceService = Depends(get_source_service)):
    ok = service.delete_source(source_key)
    if not ok:
        raise HTTPException(status_code=404, detail="Source not found")


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

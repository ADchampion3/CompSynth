"""Sources API router."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from comp_synth.api.deps import get_source_service
from comp_synth.api.schemas import ErrorDetail, SourceResponse
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

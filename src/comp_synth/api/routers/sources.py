"""Sources API router."""

from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from comp_synth.api.deps import get_schema_store, get_session, get_source_service
from comp_synth.api.schemas import (
    ErrorDetail,
    LlmSelectorsUpdateRequest,
    ReextractSelectorsRequest,
    ReextractSelectorsResponse,
    SourceCreateRequest,
    SourceResponse,
    SourceUpdateRequest,
)
from comp_synth.crawlers.extractors import DOMExtractor
from comp_synth.schema.site_chema import SiteSchema
from comp_synth.services.source_service import SourceService
from comp_synth.store.repositories.source_crawl_outcome_repository import (
    SourceCrawlOutcomeRepository,
)
from comp_synth.store.schema_store import SchemaStore

router = APIRouter(tags=["sources"])


def _source_to_response(source, health=None, llm_selectors=None) -> SourceResponse:
    data = dict(
        source_key=source.source_key,
        source_type=source.source_type,
        url=source.url,
        name=source.name,
        enabled=source.enabled,
        selectors=source.selectors,
        llm_selectors=llm_selectors,
        javascript=source.javascript,
    )
    if health is not None:
        data["crawl_status"] = health.status
        data["last_crawled_at"] = health.last_crawled_at
        data["last_new_item_count"] = health.last_new_item_count
        data["recent_zero_days"] = health.recent_zero_days
        data["last_error"] = health.last_error
    return SourceResponse(**data)


def _site_name_from_url(url: str) -> str:
    return urlparse(url).netloc


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(
    service: SourceService = Depends(get_source_service),
    session: Session = Depends(get_session),
    schema_store: SchemaStore = Depends(get_schema_store),
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
        llm_selectors = None
        if s.source_type in ("web", "javascript"):
            schema = schema_store.get(_site_name_from_url(s.url))
            if schema and schema.selectors:
                llm_selectors = schema.selectors
        result.append(_source_to_response(s, health=health, llm_selectors=llm_selectors))
    return result


@router.post("/sources", response_model=SourceResponse, status_code=201)
def create_source(body: SourceCreateRequest, service: SourceService = Depends(get_source_service)):
    try:
        source = service.create_source(
            source_type=body.source_type,
            url=body.url,
            name=body.name,
            enabled=body.enabled,
            javascript=body.javascript,
            selectors=body.selectors,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _source_to_response(source)


@router.post(
    "/sources/reextract-selectors",
    response_model=ReextractSelectorsResponse,
)
async def reextract_selectors(
    body: ReextractSelectorsRequest,
    service: SourceService = Depends(get_source_service),
    schema_store: SchemaStore = Depends(get_schema_store),
):
    sources = service.list_sources()
    source = next((s for s in sources if s.source_key == body.source_key), None)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.source_type not in ("web", "javascript"):
        raise HTTPException(status_code=400, detail="Only web/javascript sources support selector extraction")

    site_name = _site_name_from_url(source.url)

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(source.url, headers={"User-Agent": "CompSynth/1.0"})
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch {} for reextract: {}", source.url, exc)
        raise HTTPException(status_code=502, detail=f"Failed to fetch source page: {exc}") from exc

    extractor = DOMExtractor()
    selectors = await extractor.generate_list_item_selectors(html)

    if selectors:
        existing = schema_store.get(site_name)
        if existing:
            schema_store.update_selectors(site_name, selectors)
        else:
            schema_store.save(SiteSchema(
                site_name=site_name,
                site_url=source.url,
                selectors=selectors,
            ))
        schema_store.mark_llm_called(site_name)

    return ReextractSelectorsResponse(site_name=site_name, selectors=selectors or [])


@router.put("/sources/llm-selectors")
def update_llm_selectors(
    body: LlmSelectorsUpdateRequest,
    service: SourceService = Depends(get_source_service),
    schema_store: SchemaStore = Depends(get_schema_store),
):
    sources = service.list_sources()
    source = next((s for s in sources if s.source_key == body.source_key), None)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    site_name = _site_name_from_url(source.url)
    existing = schema_store.get(site_name)
    if existing:
        schema_store.update_selectors(site_name, body.selectors)
    else:
        schema_store.save(SiteSchema(
            site_name=site_name,
            site_url=source.url,
            selectors=body.selectors,
        ))
    return {"updated": True, "site_name": site_name}


@router.put("/sources/{source_key:path}", response_model=SourceResponse)
def update_source(
    source_key: str,
    body: SourceUpdateRequest,
    service: SourceService = Depends(get_source_service),
):
    source_key = source_key.removeprefix("api/sources/")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    source = service.update_source(source_key, **fields)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_to_response(source)


@router.delete("/sources/{source_key:path}", status_code=204)
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

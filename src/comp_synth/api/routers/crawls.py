"""Crawl runs API router."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from comp_synth.api.deps import get_crawl_service
from comp_synth.api.mappers import crawl_run_source_to_response, crawl_run_to_response
from comp_synth.api.schemas import CrawlRunDetailResponse, CrawlRunResponse, ErrorDetail
from comp_synth.services.crawl_service import CrawlService

router = APIRouter(tags=["crawls"])


async def _run_crawl_background() -> None:
    import logging

    from comp_synth.api.deps import get_crawl_service

    logger = logging.getLogger(__name__)
    service = get_crawl_service()
    try:
        await service.run_all()
    except Exception:
        logger.exception("Background crawl failed")


@router.post("/crawls")
def start_crawl(background_tasks: BackgroundTasks, service: CrawlService = Depends(get_crawl_service)):
    if service.has_running_crawl():
        raise HTTPException(status_code=409, detail="A crawl is already running.")
    background_tasks.add_task(_run_crawl_background)
    return {"status": "started"}


@router.get("/crawls", response_model=list[CrawlRunResponse])
def list_crawls(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: CrawlService = Depends(get_crawl_service),
):
    runs = service.list_runs(limit)
    return [crawl_run_to_response(run) for run in runs]


@router.get("/crawls/{run_id}", response_model=CrawlRunDetailResponse)
def get_crawl(
    run_id: str,
    service: CrawlService = Depends(get_crawl_service),
):
    run = service.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorDetail(
                problem="Crawl run not found",
                cause="No crawl run with that id",
                fix="List recent crawls to find valid run ids.",
            ).model_dump(),
        )
    source_runs = service.list_source_runs(run_id)
    return CrawlRunDetailResponse(
        run=crawl_run_to_response(run),
        sources=[crawl_run_source_to_response(sr) for sr in source_runs],
    )

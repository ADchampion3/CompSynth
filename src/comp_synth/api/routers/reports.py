"""Reports API router."""

from fastapi import APIRouter, Depends, HTTPException

from comp_synth.api.deps import get_report_service
from comp_synth.api.schemas import (
    ErrorDetail,
    ReportDetailResponse,
    ReportSummaryResponse,
)
from comp_synth.services.report_service import ReportService

router = APIRouter(tags=["reports"])


def _summary_to_response(report) -> ReportSummaryResponse:
    return ReportSummaryResponse(
        report_id=report.report_id,
        title=report.title,
        created_at=report.created_at,
    )


@router.get("/reports", response_model=list[ReportSummaryResponse])
def list_reports(service: ReportService = Depends(get_report_service)):
    reports = service.list_reports()
    return [_summary_to_response(r) for r in reports]


@router.get("/reports/{report_id}", response_model=ReportDetailResponse)
def get_report(
    report_id: str,
    service: ReportService = Depends(get_report_service),
):
    try:
        report = service.get_report(report_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=ErrorDetail(
                problem="Invalid report id",
                cause=str(exc),
                fix="Use format digest_YYYYMMDD, e.g. digest_20260501.",
            ).model_dump(),
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=ErrorDetail(
                problem="Report file not found",
                cause=f"Markdown file for {report_id} is missing",
                fix="Generate a new report or check the output directory.",
            ).model_dump(),
        )
    return ReportDetailResponse(
        report_id=report.report_id,
        title=report.title,
        created_at=report.created_at,
        markdown=report.markdown,
    )

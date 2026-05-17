"""CompSynth CLI entry point — thin shim that delegates to the Typer app.

Backward-compat re-exports are kept so that existing imports like
``import comp_synth.main as main_module; main_module.run()`` continue to work.
"""

from __future__ import annotations

import asyncio
from datetime import timezone
from pathlib import Path

from comp_synth.api.deps import create_session_factory
from comp_synth.services.article_service import ArticleService
from comp_synth.services.crawl_service import CrawlService
from comp_synth.services.dashboard_service import DashboardService, DashboardSummary
from comp_synth.services.report_service import (
    ReportDetail,
    ReportService,
    ReportSummary,
)
from comp_synth.services.source_service import SourceService
from comp_synth.store.repositories.article_repository import ArticleRepository
from comp_synth.store.repositories.article_state_repository import (
    ArticleStateRepository,
)
from comp_synth.store.repositories.crawl_run_repository import CrawlRunRepository
from comp_synth.store.repositories.source_crawl_outcome_repository import (
    SourceCrawlOutcomeRepository,
)

# ── public API (backward compat) ────────────────────────────────────────────

__all__ = [
    "main",
    "run",
    "crawl_command",
    "dashboard",
    "notify_command",
    "serve_command",
    "sources_command",
    "reports_command",
    "SourceService",
    "ReportService",
    "CrawlService",
    "DashboardSummary",
    "ReportSummary",
    "ReportDetail",
]


async def run(db_path: Path | None = None) -> dict:
    from comp_synth.config import settings
    from comp_synth.utils.logging import logger

    logger.info("CompSynth starting")

    # Sync YAML subscriptions to DB before crawl
    source_service = SourceService(
        subscriptions_path=settings.subscriptions_path,
        source_db_path=settings.crawl_db_path,
    )
    try:
        imported = source_service.import_yaml()
        logger.info(f"Subscriptions synced: {len(imported)} sources")
    except Exception as exc:
        logger.warning(f"Subscription sync skipped: {exc}")

    result = await CrawlService(crawl_db_path=db_path).run_all()

    if result.get("errors"):
        for err in result["errors"]:
            logger.warning(f"Pipeline error: {err}")

    status = result.get("publish_results", {}).get("status", "unknown")
    if status == "skipped":
        logger.info("No new content; exiting.")
    elif status == "success":
        path = result["publish_results"].get("path", "")
        logger.info(f"Digest written: {path}")
    else:
        logger.warning(f"Pipeline finished with status: {status}")

    return result


def crawl_command(db_path: Path | None = None) -> dict:
    return _crawl_result_to_dict(asyncio.run(run(db_path)))


def notify_command(args) -> dict:
    from comp_synth.config import settings
    from comp_synth.publishers.registry import get_enabled_publishers

    channels = settings.get_channels()
    if not channels:
        return {"status": "skipped", "error": "no channels configured"}

    if getattr(args, "file", None):
        path = args.file
        if not path.exists():
            return {"status": "error", "error": f"file not found: {path}"}
        if path.suffix.lower() != ".md":
            return {"status": "error", "error": f"only .md files are supported: {path}"}
        report = path.read_text(encoding="utf-8")
    else:
        output_dir = Path(settings.output_dir)
        digests = sorted(output_dir.glob("digest_*.md"), key=lambda p: p.stat().st_mtime)
        if not digests:
            return {"status": "error", "error": "no digest found"}
        path = digests[-1]
        report = path.read_text(encoding="utf-8")

    publishers = get_enabled_publishers(channels)
    results: list[dict] = []
    for pub in publishers:
        result = asyncio.run(pub.publish(report, pub.get_config()))
        result["channel"] = pub.channel_name
        results.append(result)

    return {"status": "sent", "source": str(path), "results": results}


def serve_command(args) -> None:
    import uvicorn

    from comp_synth.api.app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port, reload=False)


def sources_command(args) -> dict:
    service = SourceService(
        subscriptions_path=getattr(args, "path", None),
        source_db_path=args.db_path,
    )
    if args.source_command == "import":
        if getattr(args, "overwrite", False):
            imported = service.overwrite_yaml(getattr(args, "path", None))
            return {"imported": len(imported), "mode": "overwrite"}
        imported = service.import_yaml(getattr(args, "path", None))
        return {"imported": len(imported)}
    if args.source_command == "export":
        exported = service.export_yaml(getattr(args, "output", None))
        return {"exported": str(exported)}
    raise SystemExit("sources requires a subcommand: import or export")


def reports_command(args) -> dict:
    service = ReportService(report_db_path=args.db_path)
    if args.report_command == "list":
        return {"reports": [_report_summary_to_dict(report) for report in service.list_reports()]}
    if args.report_command == "get":
        return _report_detail_to_dict(service.get_report(args.report_id))
    raise SystemExit("reports requires a subcommand: list or get")


def dashboard(db_path: Path | None = None) -> dict:
    from comp_synth.config import settings

    factory = create_session_factory(db_path)
    with factory() as session:
        article_repo = ArticleRepository(session)
        summary = DashboardService(
            article_service=ArticleService(article_repo, ArticleStateRepository(session)),
            crawl_run_repository=CrawlRunRepository(session),
            source_outcome_repository=SourceCrawlOutcomeRepository(session),
        ).get_summary(
            source_health_lookback_days=settings.selector_zero_refresh_lookback_days,
            source_zero_day_threshold=settings.selector_zero_refresh_days,
        )
        return _dashboard_to_dict(summary)


def _crawl_result_to_dict(result: dict) -> dict:
    publish_results = result.get("publish_results", {}) or {}
    items = result.get("new_items") or result.get("fetched_items") or result.get("raw_items") or []
    return {
        "crawl_run_id": result.get("crawl_run_id"),
        "status": publish_results.get("status", "unknown"),
        "new_items": len(items),
        "errors": [str(error) for error in result.get("errors", [])],
        "publish_path": publish_results.get("path"),
    }


def _report_summary_to_dict(report: ReportSummary) -> dict:
    return {
        "report_id": report.report_id,
        "title": report.title,
        "path": str(report.path),
    }


def _report_detail_to_dict(report: ReportDetail) -> dict:
    data = _report_summary_to_dict(report)
    data["markdown"] = report.markdown
    return data


def _dashboard_to_dict(summary: DashboardSummary) -> dict:
    return {
        "article_count": summary.article_count,
        "important_unread_count": summary.important_unread_count,
        "important_unread": [
            {
                "article_id": entry.article.id,
                "title": entry.article.title,
                "source": entry.article.source,
                "url": entry.article.url,
                "importance_score": entry.importance_score,
            }
            for entry in summary.important_unread
        ],
        "latest_crawl_run": _crawl_run_to_dict(summary.latest_crawl_run),
        "failed_sources": [
            {
                "source_key": source.source_key,
                "source_type": source.source_type,
                "source_url": source.source_url,
                "status": source.status,
                "new_items": source.new_items,
                "error_text": source.error_text,
            }
            for source in summary.failed_sources
        ],
        "stale_running_runs": [_crawl_run_to_dict(run) for run in summary.stale_running_runs],
        "unhealthy_sources": [
            {
                "source_key": source.source_key,
                "source_type": source.source_type,
                "source_url": source.source_url,
                "status": source.status,
                "recent_zero_days": source.recent_zero_days,
                "last_error": source.last_error,
            }
            for source in summary.unhealthy_sources
        ],
    }


def _crawl_run_to_dict(run) -> dict | None:
    if run is None:
        return None
    return {
        "run_id": run.run_id,
        "scope": run.scope,
        "status": run.status,
        "new_items": run.new_items,
        "started_at": _datetime_to_iso(run.started_at),
        "finished_at": _datetime_to_iso(run.finished_at) if run.finished_at else None,
        "errors": run.errors,
        "error_text": run.error_text,
    }


def _datetime_to_iso(value) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


# ── CLI entry point ──────────────────────────────────────────────────────────

_KNOWN_COMMANDS = frozenset({
    "crawl", "serve", "dashboard", "notify",
    "status", "logs", "doctor",
    "reports", "sources", "config",
})


def main(argv: list[str] | None = None) -> None:
    """CLI entry point — delegates to the Typer app.

    For backward compat with tests that call ``main([...])`` directly,
    SystemExit is swallowed (Typer always raises it on completion).
    The real CLI entry point is ``comp_synth.cli:app`` which propagates
    exit codes to the shell.
    """
    from comp_synth.cli import app as typer_app

    args = list(argv) if argv is not None else None
    # If no known subcommand is present, run the default pipeline
    if args is not None and not any(a in _KNOWN_COMMANDS for a in args):
        args.append("default")

    try:
        typer_app(args=args)
    except SystemExit:
        pass


if __name__ == "__main__":
    main()

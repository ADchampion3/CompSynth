from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import uuid4

from comp_synth.orchestration.pipeline import run_pipeline
from comp_synth.orchestration.state import PipelineState
from comp_synth.schema.crawl_run import CrawlRun, CrawlRunSource
from comp_synth.store.database import get_engine
from comp_synth.store.models import resolve_db_path

PipelineRunner = Callable[[PipelineState | None], Awaitable[PipelineState]]


class CrawlService:
    """Application boundary for crawl pipeline operations."""

    def __init__(self, pipeline_runner: PipelineRunner = run_pipeline, crawl_db_path: Path | None = None) -> None:
        self._pipeline_runner = pipeline_runner
        self._crawl_db_path = resolve_db_path(Path(crawl_db_path), "crawl_state.db") if crawl_db_path else None
        self._session_factory = None
        if self._crawl_db_path:
            _, self._session_factory = get_engine(self._crawl_db_path, "crawl_state.db")

    async def run_all(self, initial_state: PipelineState | None = None) -> PipelineState:
        if self._session_factory is None:
            return await self._pipeline_runner(initial_state)

        run_id = str(uuid4())
        self._with_run_repository(lambda repo: repo.start(run_id, "all"))
        try:
            result = await self._pipeline_runner(initial_state)
        except Exception as exc:
            error_msg = str(exc)
            self._with_run_repository(
                lambda repo: repo.finish(
                    run_id,
                    status="failed",
                    errors=[error_msg],
                    error_text=error_msg,
                )
            )
            raise

        errors = [str(error) for error in result.get("errors", [])]
        status = "partial" if errors else "success"
        new_items = len(result.get("new_items") or result.get("fetched_items") or result.get("raw_items") or [])
        source_runs = self._source_runs_from_result(run_id, result)
        self._with_run_repository(
            lambda repo: (
                repo.finish(
                    run_id,
                    status=status,
                    new_items=new_items,
                    errors=errors,
                    error_text="\n".join(errors) if errors else None,
                ),
                [
                    repo.record_source(
                        run_id=source_run["run_id"],
                        source_key=source_run["source_key"],
                        source_type=source_run["source_type"],
                        source_url=source_run["source_url"],
                        status=source_run["status"],
                        new_items=source_run["new_items"],
                        error_text=source_run["error_text"],
                    )
                    for source_run in source_runs
                ],
            )
        )
        result["crawl_run_id"] = run_id
        return result

    def get_run(self, run_id: str) -> CrawlRun | None:
        """Get a crawl run by id."""
        self._require_db()
        return self._with_run_repository(lambda repo: repo.get(run_id))

    def list_runs(self, limit: int = 20) -> list[CrawlRun]:
        """List recent crawl runs."""
        self._require_db()
        return self._with_run_repository(lambda repo: repo.list_recent(limit))

    def list_source_runs(self, run_id: str) -> list[CrawlRunSource]:
        """List per-source child runs for a crawl run."""
        self._require_db()
        return self._with_run_repository(lambda repo: repo.list_sources(run_id))

    def _require_db(self) -> None:
        if self._session_factory is None:
            raise ValueError("crawl_db_path is required for crawl run operations")

    def _with_run_repository(self, fn):
        from comp_synth.store.repositories.crawl_run_repository import (
            CrawlRunRepository,
        )

        with self._session_factory() as session:
            result = fn(CrawlRunRepository(session))
            session.commit()
            return result

    def _source_runs_from_result(self, run_id: str, result: PipelineState) -> list[dict]:
        sources = result.get("sources", []) or []
        source_counts = result.get("source_counts", {}) or {}
        errors_by_source = self._errors_by_source(result.get("errors", []) or [])
        source_runs = []
        for source in sources:
            source_key = str(source.get("name") or source.get("url") or "unknown")
            error_text = errors_by_source.get(source_key)
            source_runs.append(
                {
                    "run_id": run_id,
                    "source_key": source_key,
                    "source_type": str(source.get("type", "unknown")),
                    "source_url": str(source.get("url", "")),
                    "status": "failed" if error_text else "success",
                    "new_items": int(source_counts.get(source_key, 0)),
                    "error_text": error_text,
                }
            )
        return source_runs

    def _errors_by_source(self, errors: list[str]) -> dict[str, str]:
        errors_by_source = {}
        for error in errors:
            if not error.startswith("[") or "]" not in error:
                continue
            source_key, message = error[1:].split("]", 1)
            errors_by_source[source_key] = message.strip()
        return errors_by_source

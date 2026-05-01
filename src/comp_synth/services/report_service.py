import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from comp_synth.config import settings
from comp_synth.schema.report import ReportMetadata
from comp_synth.store.migrations import bootstrap_database
from comp_synth.store.models import resolve_db_path

_REPORT_ID_PATTERN = re.compile(r"^digest_(\d{8})$")


@dataclass(frozen=True)
class ReportSummary:
    report_id: str
    title: str
    path: Path
    created_at: datetime


@dataclass(frozen=True)
class ReportDetail(ReportSummary):
    markdown: str


class ReportService:
    """Read generated digest reports from the configured output directory."""

    def __init__(self, output_dir: Path | None = None, report_db_path: Path | None = None) -> None:
        self._output_dir = Path(output_dir or settings.output_dir)
        self._report_db_path = resolve_db_path(Path(report_db_path), "crawl_state.db") if report_db_path else None
        self._engine = None
        self._session_factory = None
        if self._report_db_path:
            self._init_db()

    def list_reports(self) -> list[ReportSummary]:
        if self._session_factory is not None and self._has_report_metadata():
            return [
                self._summary_from_metadata(metadata)
                for metadata in self._with_report_repository(lambda repo: repo.list_recent())
            ]

        reports = [
            self._summary_from_path(path)
            for path in self._output_dir.glob("digest_*.md")
            if _REPORT_ID_PATTERN.fullmatch(path.stem)
        ]
        return sorted(reports, key=lambda report: report.report_id, reverse=True)

    def get_report(self, report_id: str) -> ReportDetail:
        self._validate_report_id(report_id)
        if self._session_factory is not None:
            metadata = self._with_report_repository(lambda repo: repo.get(report_id))
            if metadata is not None:
                path = metadata.markdown_path
                if not path.exists():
                    raise FileNotFoundError(path)
                return ReportDetail(
                    report_id=metadata.report_id,
                    title=metadata.title,
                    path=metadata.markdown_path,
                    created_at=metadata.created_at,
                    markdown=path.read_text(encoding="utf-8"),
                )

        path = self._output_dir / f"{report_id}.md"
        if not path.exists():
            raise FileNotFoundError(path)

        summary = self._summary_from_path(path)
        return ReportDetail(
            report_id=summary.report_id,
            title=summary.title,
            path=summary.path,
            created_at=summary.created_at,
            markdown=path.read_text(encoding="utf-8"),
        )

    def record_report(
        self,
        report_id: str,
        title: str,
        markdown_path: Path,
        date_from: date | None = None,
        date_to: date | None = None,
        filters: dict | None = None,
    ) -> ReportSummary:
        """Persist generated report metadata."""
        self._validate_report_id(report_id)
        self._require_db()
        metadata = self._with_report_repository(
            lambda repo: repo.save(
                report_id=report_id,
                title=title,
                markdown_path=markdown_path,
                date_from=date_from,
                date_to=date_to,
                filters=filters,
            )
        )
        return self._summary_from_metadata(metadata)

    def _summary_from_path(self, path: Path) -> ReportSummary:
        self._validate_report_id(path.stem)
        return ReportSummary(
            report_id=path.stem,
            title=self._title_from_report_id(path.stem),
            path=path,
            created_at=datetime.fromtimestamp(path.stat().st_mtime),
        )

    def _summary_from_metadata(self, metadata: ReportMetadata) -> ReportSummary:
        return ReportSummary(
            report_id=metadata.report_id,
            title=metadata.title,
            path=metadata.markdown_path,
            created_at=metadata.created_at,
        )

    def _title_from_report_id(self, report_id: str) -> str:
        match = self._validate_report_id(report_id)
        date_value = datetime.strptime(match.group(1), "%Y%m%d").date()
        return f"Digest {date_value.isoformat()}"

    def _validate_report_id(self, report_id: str) -> re.Match[str]:
        match = _REPORT_ID_PATTERN.fullmatch(report_id)
        if not match:
            raise ValueError(f"Invalid report id: {report_id}")
        return match

    def _init_db(self) -> None:
        self._report_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{self._report_db_path}", echo=False)
        bootstrap_database(self._engine)
        self._session_factory = sessionmaker(bind=self._engine)

    def _require_db(self) -> None:
        if self._session_factory is None:
            raise ValueError("report_db_path is required for report metadata operations")

    def _with_report_repository(self, fn):
        from comp_synth.store.repositories.report_repository import ReportRepository

        with self._session_factory() as session:
            result = fn(ReportRepository(session))
            session.commit()
            return result

    def _has_report_metadata(self) -> bool:
        return bool(self._with_report_repository(lambda repo: repo.count()))

"""Report metadata domain schema."""

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


@dataclass(frozen=True)
class ReportMetadata:
    report_id: str
    title: str
    markdown_path: Path
    created_at: datetime
    date_from: date | None = None
    date_to: date | None = None
    filters: dict = field(default_factory=dict)

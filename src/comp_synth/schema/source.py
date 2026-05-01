"""Source configuration domain schema."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceConfig:
    source_key: str
    source_type: str
    url: str
    name: str | None = None
    enabled: bool = True
    selectors: list[dict[str, str]] | None = None
    javascript: bool = False
    raw_config: dict[str, Any] | None = None

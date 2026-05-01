from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from comp_synth.config import settings
from comp_synth.orchestration.content_manager import normalize_selectors
from comp_synth.schema.source import SourceConfig
from comp_synth.store.migrations import bootstrap_database
from comp_synth.store.models import resolve_db_path


class SourceService:
    """Read configured subscription sources."""

    def __init__(self, subscriptions_path: Path | None = None, source_db_path: Path | None = None) -> None:
        self._subscriptions_path = Path(subscriptions_path or settings.subscriptions_path)
        self._source_db_path = resolve_db_path(Path(source_db_path), "crawl_state.db") if source_db_path else None
        self._engine = None
        self._session_factory = None
        if self._source_db_path:
            self._init_db()

    def list_sources(self) -> list[SourceConfig]:
        if self._session_factory is not None and self._has_managed_sources():
            return self._with_source_repository(lambda repo: repo.list())

        return self._read_yaml_sources(self._subscriptions_path)

    def import_yaml(self, subscriptions_path: Path | None = None) -> list[SourceConfig]:
        """Import YAML subscriptions into the managed sources database."""
        self._require_db()
        sources = self._read_yaml_sources(Path(subscriptions_path or self._subscriptions_path))
        self._with_source_repository(lambda repo: [repo.save(source) for source in sources])
        return sources

    def export_yaml(self, output_path: Path | None = None, include_archived: bool = False) -> Path:
        """Export managed database sources to subscriptions-compatible YAML."""
        self._require_db()
        sources = self._with_source_repository(lambda repo: repo.list(include_archived=include_archived))
        data = {"sources": [self._to_yaml_source(source) for source in sources]}
        target = Path(output_path or self._subscriptions_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)
        return target

    def _init_db(self) -> None:
        self._source_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{self._source_db_path}", echo=False)
        bootstrap_database(self._engine)
        self._session_factory = sessionmaker(bind=self._engine)

    def _require_db(self) -> None:
        if self._session_factory is None:
            raise ValueError("source_db_path is required for managed source operations")

    def _with_source_repository(self, fn):
        from comp_synth.store.repositories.source_repository import SourceRepository

        with self._session_factory() as session:
            result = fn(SourceRepository(session))
            session.commit()
            return result

    def _has_managed_sources(self) -> bool:
        return bool(self._with_source_repository(lambda repo: repo.count()))

    def _read_yaml_sources(self, path: Path) -> list[SourceConfig]:
        if not path.exists():
            return []

        with path.open(encoding="utf-8") as file:
            config = yaml.safe_load(file) or {}

        sources = config.get("sources", [])
        if not isinstance(sources, list):
            raise ValueError("sources must be a list")

        return [self._to_source_config(source) for source in sources]

    def _to_yaml_source(self, source: SourceConfig) -> dict[str, Any]:
        data = dict(source.raw_config or {})
        data["type"] = source.source_type
        data["url"] = source.url
        if source.name:
            data["name"] = source.name
        else:
            data.pop("name", None)
        if not source.enabled:
            data["enabled"] = False
        else:
            data.pop("enabled", None)
        if source.selectors:
            data["selectors"] = source.selectors
        else:
            data.pop("selectors", None)
        if source.javascript:
            data["javascript"] = True
        else:
            data.pop("javascript", None)
        return data

    def _to_source_config(self, source: Any) -> SourceConfig:
        if not isinstance(source, dict):
            raise ValueError("sources entries must be mappings")

        url = str(source.get("url", ""))
        name_value = source.get("name")
        name = str(name_value) if name_value else None
        source_type = str(source.get("type", "web"))

        return SourceConfig(
            source_key=name or url or "unknown",
            source_type=source_type,
            url=url,
            name=name,
            enabled=bool(source.get("enabled", True)),
            selectors=normalize_selectors(source.get("selectors")),
            javascript=bool(source.get("javascript", False)),
            raw_config=dict(source),
        )

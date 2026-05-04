from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from comp_synth.config import settings
from comp_synth.orchestration.content_manager import normalize_selectors
from comp_synth.schema.source import SourceConfig
from comp_synth.store.migrations import bootstrap_database
from comp_synth.store.models import resolve_db_path


class SourceService:
    """Source configuration with YAML as source of truth and DB as runtime cache.

    - On app startup: YAML → DB (full overwrite)
    - On API writes: DB + export_yaml() (keep YAML in sync)
    - On API reads: from DB
    """

    def __init__(self, subscriptions_path: Path | None = None, source_db_path: Path | None = None) -> None:
        self._subscriptions_path = Path(subscriptions_path or settings.subscriptions_path)
        self._source_db_path = resolve_db_path(Path(source_db_path), "crawl_state.db") if source_db_path else None
        self._engine = None
        self._session_factory = None
        if self._source_db_path:
            self._init_db()

    def list_sources(self) -> list[SourceConfig]:
        if self._session_factory is not None:
            return self._with_source_repository(lambda repo: repo.list())
        return self._read_yaml_sources(self._subscriptions_path)

    def create_source(self, source_type: str, url: str, name: str | None = None, enabled: bool = True, javascript: bool = False, selectors: list[dict[str, str]] | None = None) -> SourceConfig:
        self._require_db()
        raw = {"type": source_type, "url": url, "enabled": enabled, "javascript": javascript, **({"name": name} if name else {}), **({"selectors": selectors} if selectors else {})}
        source = SourceConfig(
            source_key=name or url,
            source_type=source_type,
            url=url,
            name=name,
            enabled=enabled,
            selectors=selectors,
            javascript=javascript,
            raw_config=raw,
        )
        self._with_source_repository(lambda repo: repo.save(source))
        return source

    def update_source(self, source_key: str, **fields) -> SourceConfig | None:
        self._require_db()
        return self._with_source_repository(lambda repo: self._update_in_repo(repo, source_key, fields))

    def _update_in_repo(self, repo, source_key: str, fields: dict) -> SourceConfig | None:
        existing = repo.get(source_key)
        if existing is None:
            return None
        raw = dict(existing.raw_config or {})
        selectors = fields.get("selectors", existing.selectors)
        if "selectors" in fields:
            raw["selectors"] = selectors
        updated = SourceConfig(
            source_key=source_key,
            source_type=fields.get("source_type", existing.source_type),
            url=fields.get("url", existing.url),
            name=fields.get("name", existing.name),
            enabled=fields.get("enabled", existing.enabled),
            selectors=selectors,
            javascript=fields.get("javascript", existing.javascript),
            raw_config=raw,
        )
        repo.save(updated)
        return updated

    def delete_source(self, source_key: str) -> bool:
        self._require_db()
        return self._with_source_repository(lambda repo: repo.archive(source_key))

    def import_yaml(self, subscriptions_path: Path | None = None) -> list[SourceConfig]:
        """Import YAML subscriptions into the managed sources database (upsert)."""
        self._require_db()
        sources = self._read_yaml_sources(Path(subscriptions_path or self._subscriptions_path))
        self._with_source_repository(lambda repo: [repo.save(source) for source in sources])
        logger.info("YAML → DB 同步完成: {count} 条", count=len(sources))
        return sources

    def export_yaml(self, output_path: Path | None = None, include_archived: bool = False) -> Path:
        """Export managed database sources to subscriptions-compatible YAML."""
        self._require_db()
        sources = self._with_source_repository(lambda repo: repo.list(include_archived=include_archived))
        data = {"sources": [self._to_yaml_source(source) for source in sources]}
        target = Path(output_path or self._subscriptions_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)
        tmp.replace(target)
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

"""Service layer for settings management."""

from pathlib import Path

from comp_synth.config import Settings
from comp_synth.store.repositories.settings_repository import SettingsRepository

MASKED_SENTINEL = "***configured***"

SENSITIVE_FIELDS = {"openai_api_key", "anthropic_api_key"}

PATH_FIELDS = {"log_dir", "data_dir", "crawl_db_path", "site_schema_db_path", "subscriptions_path", "output_dir"}


def _sync_to_env(
    overrides: dict[str, str],
    remove_keys: set[str] | None = None,
    env_path: Path | None = None,
) -> Path:
    """Write current DB overrides into the .env file.

    - Keys in *overrides* are updated in-place or appended.
    - Keys in *remove_keys* (bare lowercase names) are removed from the file.
    - All other lines (comments, non-schema vars) are preserved untouched.
    """
    path = Path(env_path or ".env")
    managed_lower = {k.lower() for k in SETTINGS_SCHEMA}
    remove_lower = {k.lower() for k in (remove_keys or set())}

    lines: list[str] = []
    written: set[str] = set()

    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                key = stripped.split("=", 1)[0].strip()
                bare_lower = key.removeprefix("COMPSYNTH_").lower()
                if key.upper().startswith("COMPSYNTH_") and bare_lower in managed_lower:
                    if bare_lower in overrides:
                        lines.append(f"{key}={overrides[bare_lower]}")
                        written.add(bare_lower)
                        continue
                    if bare_lower in remove_lower:
                        continue  # omit this line
            lines.append(line)

    # Add overrides not yet in file (use uppercase convention)
    for bare_key, value in overrides.items():
        if bare_key not in written:
            lines.append(f"COMPSYNTH_{bare_key.upper()}={value}")

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path

SETTINGS_SCHEMA = {
    "llm_provider": {"type": "select", "group": "llm", "label": "Provider", "sensitive": False, "description": "LLM provider type", "default": "openai", "options": ["openai", "anthropic"]},
    "openai_api_key": {"type": "string", "group": "llm", "label": "API Key", "sensitive": True, "description": "OpenAI 兼容接口的 API Key", "default": "", "provider": "openai"},
    "openai_base_url": {"type": "string", "group": "llm", "label": "Base URL", "sensitive": False, "description": "OpenAI 兼容接口地址", "default": "https://api.openai.com/v1", "provider": "openai"},
    "anthropic_api_key": {"type": "string", "group": "llm", "label": "API Key", "sensitive": True, "description": "Anthropic Claude API Key", "default": "", "provider": "anthropic"},
    "anthropic_base_url": {"type": "string", "group": "llm", "label": "Base URL", "sensitive": False, "description": "Anthropic API 接口地址（可选）", "default": "", "provider": "anthropic"},
    "model": {"type": "string", "group": "llm", "label": "Model", "sensitive": False, "description": "LLM model identifier", "default": "gpt-4o-mini", "provider_defaults": {"openai": "gpt-4o-mini", "anthropic": "claude-sonnet-4-20250514"}},
    "request_timeout": {"type": "integer", "group": "crawler", "label": "Request Timeout", "sensitive": False, "description": "HTTP request timeout in seconds", "default": 30, "constraints": {"minimum": 5, "maximum": 300}},
    "max_concurrent_requests": {"type": "integer", "group": "crawler", "label": "Max Concurrent Requests", "sensitive": False, "description": "Maximum parallel HTTP requests", "default": 5, "constraints": {"minimum": 1, "maximum": 50}},
    "list_page_time_threshold_days": {"type": "integer", "group": "crawler", "label": "List Page Time Threshold", "sensitive": False, "description": "Skip articles older than this many days", "default": 7, "constraints": {"minimum": 1, "maximum": 90}},
    "list_page_count_threshold": {"type": "integer", "group": "crawler", "label": "List Page Count Threshold", "sensitive": False, "description": "Maximum articles to extract from list pages", "default": 20, "constraints": {"minimum": 1, "maximum": 100}},
    "log_dir": {"type": "string", "group": "storage", "label": "Log Directory", "sensitive": False, "description": "Directory for log files", "default": "./logs"},
    "data_dir": {"type": "string", "group": "storage", "label": "Data Directory", "sensitive": False, "description": "Root data directory", "default": "./data"},
    "crawl_db_path": {"type": "string", "group": "storage", "label": "Crawl DB Path", "sensitive": False, "description": "SQLite crawl state database path", "default": "./data/crawl_state.db"},
    "subscriptions_path": {"type": "string", "group": "output", "label": "Subscriptions Path", "sensitive": False, "description": "Path to subscriptions YAML file", "default": "./subscriptions.yaml"},
    "output_dir": {"type": "string", "group": "output", "label": "Output Directory", "sensitive": False, "description": "Directory for generated reports", "default": "./output"},
}


class SettingsService:
    def __init__(self, repository: SettingsRepository):
        self._repo = repository

    def get_effective_settings(self) -> dict[str, str]:
        """Merge DB overrides onto Settings defaults, masking sensitive fields."""
        defaults = self._defaults_from_model()
        overrides = self._repo.load()
        if overrides:
            merged = {**defaults, **overrides}
        else:
            merged = dict(defaults)
        for field in SENSITIVE_FIELDS:
            if merged.get(field):
                merged[field] = MASKED_SENTINEL
        return merged

    def get_schema(self) -> dict:
        """Return field metadata for UI rendering."""
        return {"fields": SETTINGS_SCHEMA}

    def update_settings(self, updates: dict[str, str]) -> dict:
        """Validate updates, persist to DB, return masked effective settings.

        Rejects masked sentinel values with 422.
        Validates via Pydantic model before persisting.
        Only stores fields that are present in updates (absence = unchanged).
        """
        errors: dict[str, str] = {}

        for key, value in updates.items():
            if key not in SETTINGS_SCHEMA:
                errors[key] = f"Unknown setting: {key}"
                continue
            if SENSITIVE_FIELDS.intersection({key}) and value == MASKED_SENTINEL:
                errors[key] = "Cannot set field to masked value"
            if key in PATH_FIELDS:
                normalized = value.replace("\\", "/")
                if ".." in normalized.split("/"):
                    errors[key] = "Path must not contain '..' segments"

        if errors:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail=errors)

        current = self._repo.load() or {}
        for key, value in updates.items():
            current[key] = value

        self._validate_against_model(current)

        self._repo.save(current)
        _sync_to_env(current)
        self._apply_runtime(current)
        return self.get_effective_settings()

    def reset_group(self, group: str) -> dict:
        """Remove overrides for a group, reverting to defaults."""
        current = self._repo.load() or {}
        keys_in_group = [k for k, v in SETTINGS_SCHEMA.items() if v["group"] == group]
        for key in keys_in_group:
            current.pop(key, None)
        if current:
            self._repo.save(current)
        else:
            self._repo.delete()
        _sync_to_env(current, remove_keys=set(keys_in_group))
        effective = current if current else None
        self._apply_runtime(effective)
        return self.get_effective_settings()

    def _defaults_from_model(self) -> dict[str, str]:
        defaults: dict[str, str] = {}
        for k, v in SETTINGS_SCHEMA.items():
            defaults[k] = str(v.get("default", ""))
        return defaults

    def _validate_against_model(self, data: dict[str, str]) -> None:
        """Validate the full override set by constructing a Settings model."""
        defaults = self._defaults_from_model()
        merged = {**defaults, **data}
        settings_fields = Settings.model_fields.keys()
        validation_data = {k: v for k, v in merged.items() if k in settings_fields}
        try:
            Settings(**validation_data)
        except Exception as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail={"validation": str(exc)})

    @staticmethod
    def _apply_runtime(overrides: dict[str, str] | None) -> None:
        """Update in-memory settings and rebuild LLM registry."""
        from comp_synth.config import apply_db_overrides

        defaults = {k: str(v.get("default", "")) for k, v in SETTINGS_SCHEMA.items()}
        merged = {**defaults, **(overrides or {})}
        apply_db_overrides(merged)

        import comp_synth.llm_provider.registry as _mod
        from comp_synth.config import settings as _s
        from comp_synth.llm_provider.registry import LLMRegistry

        _mod.llm_registry = LLMRegistry(_s.model_dump())

"""Service layer for settings management."""

from comp_synth.config import Settings
from comp_synth.store.repositories.settings_repository import SettingsRepository

MASKED_SENTINEL = "***configured***"

SENSITIVE_FIELDS = {"openai_api_key", "anthropic_api_key"}

PATH_FIELDS = {"log_dir", "data_dir", "chroma_persist_dir", "crawl_db_path", "site_schema_db_path", "subscriptions_path", "output_dir"}

SETTINGS_SCHEMA = {
    "openai_api_key": {"type": "string", "group": "llm", "label": "OpenAI API Key", "sensitive": True, "description": "API key for OpenAI-compatible LLM provider", "default": ""},
    "openai_base_url": {"type": "string", "group": "llm", "label": "OpenAI Base URL", "sensitive": False, "description": "Base URL for OpenAI-compatible API", "default": "https://api.openai.com/v1"},
    "anthropic_api_key": {"type": "string", "group": "llm", "label": "Anthropic API Key", "sensitive": True, "description": "API key for Anthropic Claude", "default": ""},
    "anthropic_base_url": {"type": "string", "group": "llm", "label": "Anthropic Base URL", "sensitive": False, "description": "Base URL for Anthropic API", "default": ""},
    "model": {"type": "string", "group": "llm", "label": "Model", "sensitive": False, "description": "LLM model identifier", "default": "gpt-4o-mini"},
    "request_timeout": {"type": "integer", "group": "crawler", "label": "Request Timeout", "sensitive": False, "description": "HTTP request timeout in seconds", "default": 30, "constraints": {"minimum": 5, "maximum": 300}},
    "max_concurrent_requests": {"type": "integer", "group": "crawler", "label": "Max Concurrent Requests", "sensitive": False, "description": "Maximum parallel HTTP requests", "default": 5, "constraints": {"minimum": 1, "maximum": 50}},
    "list_page_time_threshold_days": {"type": "integer", "group": "crawler", "label": "List Page Time Threshold", "sensitive": False, "description": "Skip articles older than this many days", "default": 7, "constraints": {"minimum": 1, "maximum": 90}},
    "list_page_count_threshold": {"type": "integer", "group": "crawler", "label": "List Page Count Threshold", "sensitive": False, "description": "Maximum articles to extract from list pages", "default": 20, "constraints": {"minimum": 1, "maximum": 100}},
    "vector_ttl_days": {"type": "integer", "group": "storage", "label": "Vector TTL Days", "sensitive": False, "description": "Days before vectors are cleaned up", "default": 30, "constraints": {"minimum": 1, "maximum": 365}},
    "log_dir": {"type": "string", "group": "storage", "label": "Log Directory", "sensitive": False, "description": "Directory for log files", "default": "./logs"},
    "data_dir": {"type": "string", "group": "storage", "label": "Data Directory", "sensitive": False, "description": "Root data directory", "default": "./data"},
    "chroma_persist_dir": {"type": "string", "group": "storage", "label": "Chroma Persist Directory", "sensitive": False, "description": "ChromaDB persistence directory", "default": "./data/chroma"},
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
        return self.get_effective_settings()

    def _defaults_from_model(self) -> dict[str, str]:
        s = Settings()
        return {k: str(getattr(s, k)) for k in SETTINGS_SCHEMA}

    def _validate_against_model(self, data: dict[str, str]) -> None:
        """Validate the full override set by constructing a Settings model."""
        defaults = self._defaults_from_model()
        merged = {**defaults, **data}
        try:
            Settings(**merged)
        except Exception as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail={"validation": str(exc)})

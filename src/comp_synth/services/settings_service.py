"""Service layer for settings management.

Reads from the in-memory settings singleton (loaded from .env on startup).
Writes updates directly to .env and patches the singleton in place.
Rebuilds LLM registry when LLM-related fields change.
"""

from pathlib import Path

from comp_synth.config import Settings, settings

MASKED_SENTINEL = "***configured***"

SENSITIVE_FIELDS = {"openai_api_key", "anthropic_api_key"}

LLM_FIELDS = {
    "llm_provider", "openai_api_key", "openai_base_url",
    "anthropic_api_key", "anthropic_base_url", "model",
}

PATH_FIELDS = {"log_dir", "data_dir", "crawl_db_path", "site_schema_db_path", "subscriptions_path", "output_dir"}


def _sync_to_env(
    updates: dict[str, str],
    remove_keys: set[str] | None = None,
    env_path: Path | None = None,
) -> Path:
    """Write updated settings into the .env file.

    - Keys in *updates* are updated in-place or appended.
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
                    if bare_lower in updates:
                        lines.append(f"{key}={updates[bare_lower]}")
                        written.add(bare_lower)
                        continue
                    if bare_lower in remove_lower:
                        continue
            lines.append(line)

    for bare_key, value in updates.items():
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
    """Reads from in-memory settings; writes to .env and patches singleton."""

    def get_effective_settings(self) -> dict[str, str]:
        """Read current values from the in-memory settings singleton."""
        result: dict[str, str] = {}
        for key, field_def in SETTINGS_SCHEMA.items():
            if key in Settings.model_fields:
                result[key] = str(getattr(settings, key))
            else:
                result[key] = str(field_def.get("default", ""))
        for field in SENSITIVE_FIELDS:
            if result.get(field):
                result[field] = MASKED_SENTINEL
        return result

    def get_schema(self) -> dict:
        return {"fields": SETTINGS_SCHEMA}

    def update_settings(self, updates: dict[str, str]) -> dict:
        """Validate, write to .env, patch in-memory settings, conditionally rebuild LLM."""
        errors = self._validate_updates(updates)
        if errors:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail=errors)

        self._validate_against_model(updates)
        _sync_to_env(updates)
        _apply_runtime(updates)
        return self.get_effective_settings()

    def reset_group(self, group: str) -> dict:
        """Reset a group to Settings defaults (remove from .env, re-read)."""
        keys_in_group = [k for k, v in SETTINGS_SCHEMA.items() if v["group"] == group]
        _sync_to_env({}, remove_keys=set(keys_in_group))
        _apply_runtime_reset(set(keys_in_group))
        return self.get_effective_settings()

    def _validate_updates(self, updates: dict[str, str]) -> dict[str, str]:
        errors: dict[str, str] = {}
        for key, value in updates.items():
            if key not in SETTINGS_SCHEMA:
                errors[key] = f"Unknown setting: {key}"
                continue
            if key in SENSITIVE_FIELDS and value == MASKED_SENTINEL:
                errors[key] = "Cannot set field to masked value"
            if key in PATH_FIELDS:
                normalized = value.replace("\\", "/")
                if ".." in normalized.split("/"):
                    errors[key] = "Path must not contain '..' segments"
        return errors

    def _validate_against_model(self, updates: dict[str, str]) -> None:
        """Build a full Settings snapshot (current + updates) and validate via Pydantic."""
        snapshot = settings.model_dump()
        for key, value in updates.items():
            if key in Settings.model_fields:
                snapshot[key] = value
        settings_fields = Settings.model_fields.keys()
        validation_data = {k: v for k, v in snapshot.items() if k in settings_fields}
        try:
            Settings(**validation_data)
        except Exception as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail={"validation": str(exc)})


def _rebuild_llm_if_needed(changed_fields: set[str]) -> None:
    """Rebuild the global LLM registry when LLM-related fields change."""
    if LLM_FIELDS.intersection(changed_fields):
        import comp_synth.llm_provider.registry as _mod
        from comp_synth.config import settings as _s
        from comp_synth.llm_provider.registry import LLMRegistry

        _mod.llm_registry = LLMRegistry(_s.model_dump())


def _apply_runtime(updates: dict[str, str]) -> None:
    """Patch the in-memory settings singleton with updates, rebuild LLM if needed."""
    from comp_synth.config import apply_db_overrides

    apply_db_overrides(updates)
    _rebuild_llm_if_needed(updates)


def _apply_runtime_reset(keys: set[str]) -> None:
    """Reset specified keys on the singleton to their Settings defaults, rebuild LLM if needed."""
    fresh = Settings()
    for key in keys:
        if hasattr(fresh, key):
            setattr(settings, key, getattr(fresh, key))
    _rebuild_llm_if_needed(keys)

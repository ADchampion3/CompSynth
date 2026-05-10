"""Settings API router."""

from fastapi import APIRouter, Depends

from comp_synth.api.deps import get_settings_service
from comp_synth.services.settings_service import SettingsService

router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_settings(service: SettingsService = Depends(get_settings_service)):
    return service.get_effective_settings()


@router.patch("/settings")
def update_settings(
    updates: dict[str, str],
    service: SettingsService = Depends(get_settings_service),
):
    return service.update_settings(updates)


@router.get("/settings/schema")
def get_settings_schema(service: SettingsService = Depends(get_settings_service)):
    return service.get_schema()


@router.get("/settings/llm-status")
def llm_status():
    from comp_synth.llm_provider.registry import llm_registry

    providers = llm_registry.list_providers()
    if providers:
        return {"available": True, "model": providers[0]}
    return {"available": False, "error": "LLM provider not configured. Set API key in Settings."}

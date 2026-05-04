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

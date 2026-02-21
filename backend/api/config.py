"""Configuration API endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.schemas.config import ConfigResponse, ConfigUpdateRequest

router = APIRouter(prefix="/api/v1/config", tags=["config"])


def _mask_secret(value: str) -> str:
    """Mask configured secrets in API responses."""
    return "***" if value else ""


def _build_config_response() -> ConfigResponse:
    return ConfigResponse(
        database_url=_mask_secret(settings.database_url),
        api_key=_mask_secret(settings.api_key),
        cors_origins=settings.cors_origins,
        log_level=settings.log_level,
    )


@router.get("", response_model=ConfigResponse)
def get_config():
    """Get current runtime config with secrets redacted."""
    return _build_config_response()


@router.put("", response_model=ConfigResponse)
def update_config(update: ConfigUpdateRequest):
    """Update runtime config values.

    Note: this updates in-memory settings for the running process.
    """
    updates = update.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(settings, field, value)

    return _build_config_response()

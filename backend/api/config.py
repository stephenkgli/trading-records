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
        ibkr={
            "flex_token": _mask_secret(settings.ibkr_flex_token),
            "query_id": settings.ibkr_query_id,
            "schedule": settings.ibkr_schedule,
            "poll_interval_seconds": settings.ibkr_poll_interval_seconds,
            "poll_max_attempts": settings.ibkr_poll_max_attempts,
        },
        tradovate={
            "environment": settings.tradovate_environment,
            "username": _mask_secret(settings.tradovate_username),
            "password": _mask_secret(settings.tradovate_password),
            "app_id": settings.tradovate_app_id,
            "client_id": _mask_secret(settings.tradovate_client_id),
            "client_secret": _mask_secret(settings.tradovate_client_secret),
            "device_id": _mask_secret(settings.tradovate_device_id),
            "schedule": settings.tradovate_schedule,
        },
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

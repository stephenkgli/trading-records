"""Settings loader."""

from __future__ import annotations

from functools import lru_cache

from backend.config.base import BaseAppSettings


@lru_cache
def get_settings() -> BaseAppSettings:
    """Load application settings."""
    return BaseAppSettings()


settings = get_settings()

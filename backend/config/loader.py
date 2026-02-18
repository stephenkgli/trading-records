"""Settings loader and environment resolution."""

from __future__ import annotations

import os
from functools import lru_cache

from backend.config.base import BaseAppSettings
from backend.config.environments import DevSettings, ProdSettings, TestSettings


def _resolve_environment() -> str:
    """Resolve the current runtime environment name."""
    env = os.getenv("APP_ENV", "").strip().lower()
    if env:
        return env
    if os.getenv("PYTEST_CURRENT_TEST"):
        return "test"
    return "dev"


@lru_cache
def get_settings() -> BaseAppSettings:
    """Load settings based on the resolved environment."""
    env = _resolve_environment()
    if env in {"prod", "production"}:
        return ProdSettings()
    if env in {"test", "testing"}:
        return TestSettings()
    return DevSettings()


settings = get_settings()

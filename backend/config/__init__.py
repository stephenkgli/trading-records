"""Application configuration package.

This package provides environment-aware configuration using Pydantic Settings.
The singleton `settings` instance is automatically loaded based on the APP_ENV
environment variable or runtime detection (test vs. dev).
"""

from backend.config.base import BaseAppSettings
from backend.config.environments import DevSettings, ProdSettings, TestSettings
from backend.config.loader import get_settings, settings

__all__ = [
    "BaseAppSettings",
    "DevSettings",
    "TestSettings",
    "ProdSettings",
    "get_settings",
    "settings",
]

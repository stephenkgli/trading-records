"""Application configuration package.

This package provides application configuration using Pydantic Settings.
"""

from backend.config.base import BaseAppSettings
from backend.config.loader import get_settings, settings

__all__ = [
    "BaseAppSettings",
    "get_settings",
    "settings",
]

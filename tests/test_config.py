"""Tests for config package settings loading and parsing."""

from __future__ import annotations

from backend.config.base import BaseAppSettings
from backend.config.loader import get_settings


class TestGetSettings:
    """Test settings loader behavior."""

    def test_returns_base_settings(self):
        """get_settings should return BaseAppSettings."""
        get_settings.cache_clear()
        s = get_settings()
        assert isinstance(s, BaseAppSettings)
        get_settings.cache_clear()

    def test_get_settings_is_cached(self):
        """get_settings should return the same instance due to cache."""
        get_settings.cache_clear()
        first = get_settings()
        second = get_settings()
        assert first is second
        get_settings.cache_clear()


class TestBaseAppSettings:
    """Test BaseAppSettings defaults and CORS parsing."""

    def test_default_cors_origins(self):
        """Default CORS origins should include localhost:3000 and 8000."""
        s = BaseAppSettings()
        assert "http://localhost:3000" in s.cors_origins_list
        assert "http://localhost:8000" in s.cors_origins_list

    def test_cors_origins_list_parsing(self):
        """cors_origins_list should split comma-separated origins."""
        s = BaseAppSettings(cors_origins="http://a.com, http://b.com , http://c.com")
        assert s.cors_origins_list == ["http://a.com", "http://b.com", "http://c.com"]

    def test_cors_origins_empty(self):
        """Empty CORS string should produce empty list."""
        s = BaseAppSettings(cors_origins="")
        assert s.cors_origins_list == []

    def test_default_log_level(self):
        """Default log level should be INFO."""
        s = BaseAppSettings()
        assert s.log_level == "INFO"

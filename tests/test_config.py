"""
Tests for the config package (environment resolution and settings loading).

Verifies:
1. Environment resolution based on APP_ENV
2. Fallback to test when PYTEST_CURRENT_TEST is set
3. Fallback to dev when no env vars are set
4. Correct settings class selection per environment
5. CORS origins parsing
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.config.base import BaseAppSettings
from backend.config.environments import DevSettings, ProdSettings, TestSettings
from backend.config.loader import _resolve_environment, get_settings


class TestResolveEnvironment:
    """Test the _resolve_environment helper."""

    def test_explicit_prod(self):
        """APP_ENV=prod should resolve to 'prod'."""
        with patch.dict("os.environ", {"APP_ENV": "prod"}, clear=False):
            assert _resolve_environment() == "prod"

    def test_explicit_test(self):
        """APP_ENV=test should resolve to 'test'."""
        with patch.dict("os.environ", {"APP_ENV": "test"}, clear=False):
            assert _resolve_environment() == "test"

    def test_explicit_dev(self):
        """APP_ENV=dev should resolve to 'dev'."""
        with patch.dict("os.environ", {"APP_ENV": "dev"}, clear=False):
            assert _resolve_environment() == "dev"

    def test_case_insensitive(self):
        """APP_ENV should be case-insensitive."""
        with patch.dict("os.environ", {"APP_ENV": "PROD"}, clear=False):
            assert _resolve_environment() == "prod"

    def test_fallback_to_test_when_pytest(self):
        """Should fallback to 'test' when PYTEST_CURRENT_TEST is set."""
        with patch.dict(
            "os.environ",
            {"PYTEST_CURRENT_TEST": "some_test", "APP_ENV": ""},
            clear=False,
        ):
            assert _resolve_environment() == "test"

    def test_fallback_to_dev(self):
        """Should fallback to 'dev' when no env vars match."""
        env = {"APP_ENV": ""}
        with patch.dict("os.environ", env, clear=False):
            with patch("os.getenv") as mock_getenv:
                mock_getenv.side_effect = lambda key, default="": {
                    "APP_ENV": "",
                    "PYTEST_CURRENT_TEST": None,
                }.get(key, default)
                assert _resolve_environment() == "dev"


class TestGetSettings:
    """Test that get_settings returns the correct settings class."""

    def test_returns_dev_settings_for_dev(self):
        """get_settings should return DevSettings for dev environment."""
        with patch("backend.config.loader._resolve_environment", return_value="dev"):
            get_settings.cache_clear()
            s = get_settings()
            assert isinstance(s, DevSettings)
            get_settings.cache_clear()

    def test_returns_test_settings_for_test(self):
        """get_settings should return TestSettings for test environment."""
        with patch("backend.config.loader._resolve_environment", return_value="test"):
            get_settings.cache_clear()
            s = get_settings()
            assert isinstance(s, TestSettings)
            get_settings.cache_clear()

    def test_returns_prod_settings_for_prod(self):
        """get_settings should return ProdSettings for prod environment."""
        with patch("backend.config.loader._resolve_environment", return_value="prod"):
            get_settings.cache_clear()
            s = get_settings()
            assert isinstance(s, ProdSettings)
            get_settings.cache_clear()

    def test_returns_prod_settings_for_production(self):
        """get_settings should return ProdSettings for 'production' alias."""
        with patch(
            "backend.config.loader._resolve_environment", return_value="production"
        ):
            get_settings.cache_clear()
            s = get_settings()
            assert isinstance(s, ProdSettings)
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

    def test_default_api_key_empty(self):
        """Default api_key should be empty (auth disabled)."""
        s = BaseAppSettings()
        assert s.api_key == ""

    def test_default_log_level(self):
        """Default log level should be INFO."""
        s = BaseAppSettings()
        assert s.log_level == "INFO"

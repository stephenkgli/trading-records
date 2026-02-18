"""Environment-specific settings definitions."""

from pydantic_settings import SettingsConfigDict

from backend.config.base import BaseAppSettings


class DevSettings(BaseAppSettings):
    """Development settings (uses .env.dev when present)."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.dev"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class TestSettings(BaseAppSettings):
    """Test settings (uses .env.test when present)."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.test"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class ProdSettings(BaseAppSettings):
    """Production settings (uses .env.prod when present)."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.prod"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

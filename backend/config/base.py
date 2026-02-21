"""Base application settings definitions."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppSettings(BaseSettings):
    """Base application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql://trading:trading@localhost:5432/trading_records"

    # API
    api_key: str = ""
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    # Databento
    databento_api_key: str = ""

    # Tiingo
    tiingo_api_key: str = ""

    # Cache
    ohlcv_cache_enabled: bool = True

    # Logging
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

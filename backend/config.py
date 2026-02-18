"""Application configuration using pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

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

    # IBKR Flex Query
    ibkr_flex_token: str = ""
    ibkr_query_id: str = ""
    ibkr_schedule: str = "0 6 * * *"
    ibkr_poll_interval_seconds: int = 10
    ibkr_poll_max_attempts: int = 10

    # Tradovate
    tradovate_environment: str = "demo"
    tradovate_username: str = ""
    tradovate_password: str = ""
    tradovate_app_id: str = "trading-records"
    tradovate_client_id: str = ""
    tradovate_client_secret: str = ""
    tradovate_device_id: str = ""
    tradovate_schedule: str = "0 6 * * *"

    # Logging
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

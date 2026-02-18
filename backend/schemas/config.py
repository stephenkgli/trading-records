"""Configuration API schemas."""

from __future__ import annotations

from pydantic import BaseModel


class IBKRConfigResponse(BaseModel):
    flex_token: str
    query_id: str
    schedule: str
    poll_interval_seconds: int
    poll_max_attempts: int


class TradovateConfigResponse(BaseModel):
    environment: str
    username: str
    password: str
    app_id: str
    client_id: str
    client_secret: str
    device_id: str
    schedule: str


class ConfigResponse(BaseModel):
    database_url: str
    api_key: str
    cors_origins: str
    log_level: str
    ibkr: IBKRConfigResponse
    tradovate: TradovateConfigResponse


class ConfigUpdateRequest(BaseModel):
    database_url: str | None = None
    api_key: str | None = None
    cors_origins: str | None = None
    log_level: str | None = None

    ibkr_flex_token: str | None = None
    ibkr_query_id: str | None = None
    ibkr_schedule: str | None = None
    ibkr_poll_interval_seconds: int | None = None
    ibkr_poll_max_attempts: int | None = None

    tradovate_environment: str | None = None
    tradovate_username: str | None = None
    tradovate_password: str | None = None
    tradovate_app_id: str | None = None
    tradovate_client_id: str | None = None
    tradovate_client_secret: str | None = None
    tradovate_device_id: str | None = None
    tradovate_schedule: str | None = None

"""Configuration API schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ConfigResponse(BaseModel):
    database_url: str
    api_key: str
    cors_origins: str
    log_level: str


class ConfigUpdateRequest(BaseModel):
    database_url: str | None = None
    api_key: str | None = None
    cors_origins: str | None = None
    log_level: str | None = None

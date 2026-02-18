"""API Key authentication middleware."""

from __future__ import annotations

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import settings

logger = structlog.get_logger(__name__)

# Paths that do not require authentication
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Simple API key authentication middleware.

    - All /api/v1/* endpoints require X-API-Key header.
    - /health, /docs, /openapi.json are public.
    - Static file paths (frontend) are public.
    - If API_KEY is not set, auth is disabled with a warning.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth for static files (frontend)
        if not path.startswith("/api/"):
            return await call_next(request)

        # If no API key configured, allow all (dev convenience)
        if not settings.api_key:
            return await call_next(request)

        # Check API key header
        provided_key = request.headers.get("X-API-Key", "")
        if provided_key != settings.api_key:
            logger.warning("auth_failed", path=path, method=request.method)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key"},
            )

        return await call_next(request)

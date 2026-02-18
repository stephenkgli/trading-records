"""FastAPI application entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.auth import APIKeyMiddleware
from backend.config import settings
from backend.logging_config import setup_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    setup_logging()

    if not settings.api_key:
        logger.warning(
            "api_key_not_set",
            message="API_KEY is not set. Authentication is disabled. "
            "Set API_KEY environment variable for production.",
        )

    # Start scheduler
    from backend.services.scheduler import start_scheduler, stop_scheduler

    start_scheduler()

    logger.info("app_started", cors_origins=settings.cors_origins_list)
    yield

    stop_scheduler()
    logger.info("app_shutdown")


app = FastAPI(
    title="Trading Records",
    description="Self-hosted trading records system for IBKR and Tradovate",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key Auth
app.add_middleware(APIKeyMiddleware)

# Routers
from backend.api.health import router as health_router  # noqa: E402
from backend.api.trades import router as trades_router  # noqa: E402
from backend.api.imports import router as imports_router  # noqa: E402
from backend.api.groups import router as groups_router  # noqa: E402
from backend.api.analytics import router as analytics_router  # noqa: E402

app.include_router(health_router)
app.include_router(trades_router)
app.include_router(imports_router)
app.include_router(groups_router)
app.include_router(analytics_router)

# Serve frontend static files (built React app)
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

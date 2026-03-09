"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.exceptions import register_exception_handlers
from backend.logging_config import setup_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    setup_logging()

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

register_exception_handlers(app)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    """Add security response headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Routers — aggregated from api/v1
from backend.api.v1 import v1_router  # noqa: E402

app.include_router(v1_router)

# Serve frontend static files (built React app)
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

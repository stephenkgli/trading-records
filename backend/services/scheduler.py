"""APScheduler lifecycle management.

External broker API pull jobs were removed; the scheduler is kept for future
internal periodic tasks.
"""

from __future__ import annotations

import structlog
from apscheduler.schedulers.background import BackgroundScheduler

logger = structlog.get_logger(__name__)

scheduler = BackgroundScheduler()


def start_scheduler():
    """Initialize and start the background scheduler."""
    scheduler.start()
    logger.info("scheduler_started", job_count=len(scheduler.get_jobs()))


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")

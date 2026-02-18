"""APScheduler setup for periodic data ingestion.

Schedules:
- IBKR Flex Query: configurable cron (default: daily at 6 AM UTC)
- Tradovate: configurable cron (default: daily at 6 AM UTC)

Each job includes an idempotency check to skip if already imported today.
"""

from __future__ import annotations

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.config import settings

logger = structlog.get_logger(__name__)

scheduler = BackgroundScheduler()


def _parse_cron(cron_expr: str) -> dict:
    """Parse a cron expression (5-field) into APScheduler CronTrigger kwargs."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expr}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def run_flex_query_job():
    """Scheduled job: fetch IBKR Flex Query data."""
    logger.info("scheduler_job_start", job_name="flex_query")
    try:
        from backend.ingestion.ibkr_flex import IBKRFlexIngester

        ingester = IBKRFlexIngester()
        result = ingester.fetch_and_import()
        logger.info(
            "scheduler_job_complete",
            job_name="flex_query",
            status=result.status,
            records_imported=result.records_imported,
        )
    except Exception as e:
        logger.error("scheduler_job_error", job_name="flex_query", error=str(e))


def run_tradovate_job():
    """Scheduled job: fetch Tradovate data."""
    logger.info("scheduler_job_start", job_name="tradovate")
    try:
        from backend.ingestion.tradovate import TradovateIngester

        ingester = TradovateIngester()
        result = ingester.fetch_and_import()
        logger.info(
            "scheduler_job_complete",
            job_name="tradovate",
            status=result.status,
            records_imported=result.records_imported,
        )
    except Exception as e:
        logger.error("scheduler_job_error", job_name="tradovate", error=str(e))


def start_scheduler():
    """Initialize and start the background scheduler."""
    # IBKR Flex Query schedule
    if settings.ibkr_flex_token and settings.ibkr_query_id:
        try:
            cron_kwargs = _parse_cron(settings.ibkr_schedule)
            scheduler.add_job(
                run_flex_query_job,
                trigger=CronTrigger(**cron_kwargs),
                id="flex_query",
                name="IBKR Flex Query Import",
                replace_existing=True,
            )
            logger.info(
                "scheduler_job_added",
                job_name="flex_query",
                schedule=settings.ibkr_schedule,
            )
        except Exception as e:
            logger.error("scheduler_add_job_error", job_name="flex_query", error=str(e))

    # Tradovate schedule
    if settings.tradovate_username and settings.tradovate_password:
        try:
            cron_kwargs = _parse_cron(settings.tradovate_schedule)
            scheduler.add_job(
                run_tradovate_job,
                trigger=CronTrigger(**cron_kwargs),
                id="tradovate",
                name="Tradovate Import",
                replace_existing=True,
            )
            logger.info(
                "scheduler_job_added",
                job_name="tradovate",
                schedule=settings.tradovate_schedule,
            )
        except Exception as e:
            logger.error(
                "scheduler_add_job_error", job_name="tradovate", error=str(e)
            )

    scheduler.start()
    logger.info("scheduler_started", job_count=len(scheduler.get_jobs()))


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")

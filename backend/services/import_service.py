"""Import service — orchestrates import operations.

Encapsulates all business logic for CSV uploads, Flex Query triggers,
Tradovate triggers, and import log queries. API handlers delegate here
so they only handle request/response mapping.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.ingestion.csv_importer import CSVImporter
from backend.ingestion.ibkr_flex import IBKRFlexIngester
from backend.models.import_log import ImportLog
from backend.schemas.import_result import (
    ImportLogListResponse,
    ImportLogResponse,
    ImportResult,
)

logger = structlog.get_logger(__name__)


class ImportService:
    """Service for import operations."""

    def import_csv(
        self,
        file_content: bytes | str,
        filename: str,
        db: Session,
    ) -> ImportResult:
        """Import trades from a CSV file.

        Auto-detects format (IBKR, Tradovate, Tradovate Performance).

        Args:
            file_content: Raw CSV bytes or string.
            filename: Original filename.
            db: Database session.

        Returns:
            ImportResult summary.

        Raises:
            ValueError: When format is unrecognised or input is invalid.
        """
        logger.info("csv_import_start", filename=filename, size=len(file_content))
        importer = CSVImporter()
        return importer.import_csv(file_content, filename=filename, db=db)

    def trigger_flex_query(self, db: Session) -> ImportResult:
        """Trigger an IBKR Flex Query import.

        Args:
            db: Database session.

        Returns:
            ImportResult summary.

        Raises:
            ValueError: When credentials are missing.
        """
        ingester = IBKRFlexIngester()
        return ingester.fetch_and_import(db=db)

    def trigger_tradovate(self, db: Session) -> ImportResult:
        """Trigger a Tradovate API import.

        Args:
            db: Database session.

        Returns:
            ImportResult summary.

        Raises:
            ValueError: When credentials are missing.
        """
        from backend.ingestion.tradovate import TradovateIngester

        ingester = TradovateIngester()
        return ingester.fetch_and_import(db=db)

    def list_import_logs(
        self,
        db: Session,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> ImportLogListResponse:
        """List import history with pagination.

        Args:
            db: Database session.
            page: Page number (1-indexed).
            per_page: Results per page.

        Returns:
            Paginated import log response.
        """
        count_query = select(func.count()).select_from(ImportLog)
        total = db.execute(count_query).scalar_one()

        query = (
            select(ImportLog)
            .order_by(ImportLog.started_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        logs = db.execute(query).scalars().all()

        return ImportLogListResponse(
            logs=[ImportLogResponse.model_validate(log) for log in logs],
            total=total,
            page=page,
            per_page=per_page,
        )

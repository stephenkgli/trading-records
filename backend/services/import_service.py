"""Import service — orchestrates import operations.

Encapsulates all business logic for CSV uploads and import log queries.
API handlers delegate here so they only handle request/response mapping.
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.ingestion.csv_importer import CSVImporter
from backend.models.import_log import ImportLog
from backend.models.trade import Trade
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

        # 获取这些 import_log 关联的交易记录的起止时间和 broker 信息
        log_ids = [log.id for log in logs]
        trade_stats: dict = {}
        if log_ids:
            dialect_name = db.bind.dialect.name if db.bind else ""
            if dialect_name == "postgresql":
                brokers_col = func.string_agg(
                    func.distinct(Trade.broker), ", "
                ).label("brokers")
            else:
                # SQLite: group_concat(DISTINCT x) only accepts one arg;
                # default separator is ',' so we replace to match PG output.
                brokers_col = func.replace(
                    func.group_concat(Trade.broker.distinct()), ",", ", "
                ).label("brokers")
            stats_query = (
                select(
                    Trade.import_log_id,
                    func.min(Trade.executed_at).label("date_from"),
                    func.max(Trade.executed_at).label("date_to"),
                    brokers_col,
                )
                .where(Trade.import_log_id.in_(log_ids))
                .group_by(Trade.import_log_id)
            )
            for row in db.execute(stats_query).all():
                trade_stats[row.import_log_id] = {
                    "trade_date_from": row.date_from,
                    "trade_date_to": row.date_to,
                    "broker": row.brokers,
                }

        log_responses = []
        for log in logs:
            resp = ImportLogResponse.model_validate(log)
            stats = trade_stats.get(log.id)
            if stats:
                resp.trade_date_from = stats["trade_date_from"]
                resp.trade_date_to = stats["trade_date_to"]
                resp.broker = stats["broker"]
            log_responses.append(resp)

        return ImportLogListResponse(
            logs=log_responses,
            total=total,
            page=page,
            per_page=per_page,
        )

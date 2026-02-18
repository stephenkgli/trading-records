"""Ingestion pipeline orchestrator.

Coordinates the flow: source.fetch -> validate -> dedup -> persist.
Import sources are pluggable via the ImportSource interface; adding a new
source does not require modifying this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from backend.ingestion.base import BaseIngester
from backend.ingestion.sources.base import ImportSource

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.schemas.import_result import ImportResult

logger = structlog.get_logger(__name__)


class IngestionPipeline:
    """Orchestrates import from any ImportSource through the standard pipeline.

    The pipeline delegates validation, dedup, and persistence to
    ``BaseIngester.import_records()``, keeping the flow consistent
    across all sources.
    """

    def run(
        self,
        source: ImportSource,
        *,
        db: Session | None = None,
        **source_kwargs: object,
    ) -> ImportResult:
        """Execute the full ingestion pipeline for the given source.

        Args:
            source: An ImportSource implementation that produces
                NormalizedTrade records.
            db: Optional database session.
            **source_kwargs: Passed through to ``source.fetch_normalized_trades``.

        Returns:
            ImportResult summarising the import.
        """
        logger.info("pipeline_start", source=source.source_name)

        trades = source.fetch_normalized_trades(db=db, **source_kwargs)

        # Delegate to BaseIngester for validate -> dedup -> persist
        ingester = _PipelineIngester(source_name=source.source_name)
        result = ingester.import_records(trades, db=db)

        logger.info(
            "pipeline_complete",
            source=source.source_name,
            records_imported=result.records_imported,
            records_skipped_dup=result.records_skipped_dup,
        )
        return result


class _PipelineIngester(BaseIngester):
    """Thin BaseIngester subclass whose ``source`` is set dynamically."""

    def __init__(self, source_name: str) -> None:
        self.source = source_name

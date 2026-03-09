"""Base ingester with deduplication and transaction-wrapped import.

All ingesters inherit from BaseIngester and implement the fetch + normalize logic.
The import_records() method handles validation, dedup, and atomic database insert.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence

import structlog
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.ingestion.validator import validate_batch
from backend.models.import_log import ImportLog
from backend.models.trade import Trade
from backend.schemas.import_result import ImportResult
from backend.schemas.trade import NormalizedTrade

logger = structlog.get_logger(__name__)


class BaseIngester:
    """Base class for all data ingesters.

    Subclasses must implement fetch_and_normalize() to produce NormalizedTrade records.
    The import_records() method handles validation, dedup, and transactional insert.
    """

    source: str = "unknown"

    def import_records(
        self,
        trades: list[NormalizedTrade],
        db: Session | None = None,
    ) -> ImportResult:
        """Import normalized trades into the database.

        Flow:
        1. Validate all records
        2. BEGIN TRANSACTION
        3. Deduplicate valid records against existing data
        4. Insert new records
        5. Write import_log entry
        6. COMMIT (or ROLLBACK on failure)

        Args:
            trades: List of normalized trade records.
            db: Optional existing database session. If None, creates a new one.

        Returns:
            ImportResult with summary statistics.
        """
        own_session = db is None
        if own_session:
            db = SessionLocal()

        import_log = ImportLog(
            id=uuid.uuid4(),
            source=self.source,
            status="pending",
            records_total=len(trades),
            started_at=datetime.now(timezone.utc),
        )

        try:
            # Step 1: Validate (outside transaction)
            validation = validate_batch(trades, source=self.source)

            import_log.records_failed = validation.failed_count
            if validation.errors:
                import_log.errors = validation.errors

            # Step 2–6: Transaction for dedup + insert
            tx = db.begin_nested() if db.in_transaction() else db.begin()
            try:
                with tx:
                    # Deduplicate
                    new_trades, skipped_count = self._deduplicate(
                        db, validation.valid
                    )

                    import_log.records_skipped_dup = skipped_count
                    import_log.records_imported = len(new_trades)

                    # Insert new trade records in batch
                    trade_records = [
                        Trade(
                            broker=normalized.broker,
                            broker_exec_id=normalized.broker_exec_id,
                            import_log_id=import_log.id,
                            account_id=normalized.account_id,
                            symbol=normalized.symbol,
                            underlying=normalized.underlying,
                            asset_class=normalized.asset_class,
                            side=normalized.side,
                            quantity=abs(normalized.quantity),
                            price=normalized.price,
                            commission=normalized.commission,
                            multiplier=normalized.multiplier,
                            executed_at=normalized.executed_at,
                            order_id=normalized.order_id,
                            exchange=normalized.exchange,
                            currency=normalized.currency,
                            raw_data=normalized.raw_data,
                        )
                        for normalized in new_trades
                    ]
                    if trade_records:
                        db.add_all(trade_records)

                    # Determine status
                    if validation.failed_count > 0 and len(new_trades) > 0:
                        import_log.status = "partial"
                    elif len(new_trades) == 0 and validation.failed_count > 0:
                        import_log.status = "failed"
                    else:
                        import_log.status = "success"

                    import_log.completed_at = datetime.now(timezone.utc)
                    db.add(import_log)

                if import_log.status in ("success", "partial") and new_trades:
                    self._run_post_import_hooks(db, new_trades)

                logger.info(
                    "import_completed",
                    source=self.source,
                    import_log_id=str(import_log.id),
                    records_total=import_log.records_total,
                    records_imported=import_log.records_imported,
                    records_skipped_dup=import_log.records_skipped_dup,
                    records_failed=import_log.records_failed,
                )

            except Exception:
                import_log.status = "failed"
                import_log.completed_at = datetime.now(timezone.utc)
                # Try to save the failed import log in a new transaction
                try:
                    fail_tx = db.begin_nested() if db.in_transaction() else db.begin()
                    with fail_tx:
                        db.add(import_log)
                except Exception:
                    if db.in_transaction():
                        db.rollback()
                raise

        except Exception as exc:
            logger.error(
                "import_failed",
                source=self.source,
                error=str(exc),
            )
            raise

        finally:
            if own_session:
                db.close()

        return ImportResult(
            import_log_id=import_log.id,
            source=self.source,
            status=import_log.status,
            records_total=import_log.records_total,
            records_imported=import_log.records_imported,
            records_skipped_dup=import_log.records_skipped_dup,
            records_failed=import_log.records_failed,
            errors=validation.errors,
        )

    def _run_post_import_hooks(
        self, db: Session, imported_trades: Sequence[NormalizedTrade]
    ) -> None:
        """Run post-import refresh and grouping hooks.

        Order matters: recompute groups FIRST (so trade_groups.realized_pnl
        is up-to-date), THEN refresh the materialized view which reads from
        trade_groups.

        Hooks are best-effort; failures are logged but do not fail the import.
        """
        if not imported_trades:
            return

        hook_tx = db.begin_nested() if db.in_transaction() else db.begin()
        with hook_tx:
            # 1. Recompute groups FIRST — daily_summaries view reads from trade_groups.
            try:
                from backend.services.trade_grouper import recompute_groups

                affected_pairs = {(t.account_id, t.symbol) for t in imported_trades}
                for account_id, symbol in affected_pairs:
                    recompute_groups(db=db, symbol=symbol, account_id=account_id)
            except (SQLAlchemyError, ValueError, RuntimeError) as exc:
                logger.warning(
                    "post_import_group_recompute_failed",
                    source=self.source,
                    error=str(exc),
                )

            # 2. Refresh materialized view AFTER groups are recomputed.
            bind = db.get_bind()
            if bind and bind.dialect.name == "postgresql":
                try:
                    from backend.services.analytics import refresh_daily_summaries

                    refresh_daily_summaries(db=db)
                except (SQLAlchemyError, RuntimeError) as exc:
                    logger.warning(
                        "post_import_refresh_failed",
                        source=self.source,
                        error=str(exc),
                    )

    def _deduplicate(
        self,
        db: Session,
        trades: list[NormalizedTrade],
    ) -> tuple[list[NormalizedTrade], int]:
        """Remove trades that already exist in the database.

        Uses composite key (broker, broker_exec_id) for dedup.

        Returns:
            Tuple of (new_trades, skipped_count).
        """
        if not trades:
            return [], 0

        # Collect all composite keys to check
        keys_to_check = [(t.broker, t.broker_exec_id) for t in trades]

        # Query for existing keys in batch
        existing_keys: set[tuple[str, str]] = set()
        # Process in chunks to avoid overly large IN clauses
        chunk_size = 500
        for i in range(0, len(keys_to_check), chunk_size):
            chunk = keys_to_check[i : i + chunk_size]
            brokers = [k[0] for k in chunk]
            exec_ids = [k[1] for k in chunk]

            stmt = select(Trade.broker, Trade.broker_exec_id).where(
                Trade.broker.in_(set(brokers)),
                Trade.broker_exec_id.in_(set(exec_ids)),
            )
            rows = db.execute(stmt).all()
            existing_keys.update((row[0], row[1]) for row in rows)

        new_trades = []
        skipped = 0
        for trade in trades:
            key = (trade.broker, trade.broker_exec_id)
            if key in existing_keys:
                skipped += 1
                logger.debug(
                    "dedup_skip",
                    broker=trade.broker,
                    broker_exec_id=trade.broker_exec_id,
                )
            else:
                new_trades.append(trade)
                # Add to set to handle duplicates within the same batch
                existing_keys.add(key)

        return new_trades, skipped

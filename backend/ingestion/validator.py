"""Data validation rules for normalized trades.

Validates records between normalization and deduplication.
Invalid records are not inserted but are logged in import_logs.errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

import structlog

from backend.schemas.trade import NormalizedTrade

logger = structlog.get_logger(__name__)

# Earliest valid trade date
MIN_TRADE_DATE = datetime(2000, 1, 1, tzinfo=timezone.utc)

VALID_BROKERS = {"ibkr", "tradovate"}
VALID_ASSET_CLASSES = {"stock", "future", "option", "forex"}


@dataclass
class ValidationError:
    """A single validation failure."""

    field: str
    value: str | None
    reason: str


@dataclass
class ValidationResult:
    """Result of validating a batch of trades."""

    valid: list[NormalizedTrade] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    @property
    def failed_count(self) -> int:
        return len(self.errors)


def validate_trade(trade: NormalizedTrade) -> list[ValidationError]:
    """Validate a single normalized trade against all rules.

    Returns a list of validation errors (empty if valid).
    """
    errors: list[ValidationError] = []

    # Rule 1: Required fields must be non-null and non-empty
    required_fields = {
        "symbol": trade.symbol,
        "price": trade.price,
        "quantity": trade.quantity,
        "executed_at": trade.executed_at,
        "side": trade.side,
        "broker_exec_id": trade.broker_exec_id,
    }
    for field_name, value in required_fields.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(
                ValidationError(
                    field=field_name,
                    value=str(value) if value is not None else None,
                    reason=f"{field_name} is required and must be non-empty",
                )
            )

    # Rule 2: Price must be positive (except certain forex/futures adjustments)
    if trade.price is not None and trade.price <= Decimal("0"):
        errors.append(
            ValidationError(
                field="price",
                value=str(trade.price),
                reason="price must be greater than 0",
            )
        )

    # Rule 3: Quantity must be non-zero
    if trade.quantity is not None and trade.quantity == Decimal("0"):
        errors.append(
            ValidationError(
                field="quantity",
                value=str(trade.quantity),
                reason="quantity must not be zero",
            )
        )

    # Rule 4: Timestamp sanity — not in the future, not before 2000-01-01
    if trade.executed_at is not None:
        now = datetime.now(timezone.utc)
        executed = trade.executed_at
        if executed.tzinfo is None:
            # Treat naive as UTC
            executed = executed.replace(tzinfo=timezone.utc)

        if executed > now:
            errors.append(
                ValidationError(
                    field="executed_at",
                    value=str(trade.executed_at),
                    reason="executed_at must not be in the future",
                )
            )
        if executed < MIN_TRADE_DATE:
            errors.append(
                ValidationError(
                    field="executed_at",
                    value=str(trade.executed_at),
                    reason="executed_at must not be before 2000-01-01",
                )
            )

    # Rule 5: Broker must be valid enum
    if trade.broker not in VALID_BROKERS:
        errors.append(
            ValidationError(
                field="broker",
                value=trade.broker,
                reason=f"broker must be one of {VALID_BROKERS}",
            )
        )

    # Rule 6: Asset class must be valid enum
    if trade.asset_class not in VALID_ASSET_CLASSES:
        errors.append(
            ValidationError(
                field="asset_class",
                value=trade.asset_class,
                reason=f"asset_class must be one of {VALID_ASSET_CLASSES}",
            )
        )

    return errors


def validate_batch(
    trades: list[NormalizedTrade], source: str = ""
) -> ValidationResult:
    """Validate a batch of normalized trades.

    Returns a ValidationResult containing valid trades and error details.
    """
    result = ValidationResult()

    for i, trade in enumerate(trades):
        errors = validate_trade(trade)
        if errors:
            error_dict = {
                "row": i,
                "broker_exec_id": trade.broker_exec_id,
                "errors": [
                    {"field": e.field, "value": e.value, "reason": e.reason}
                    for e in errors
                ],
            }
            result.errors.append(error_dict)
            logger.warning(
                "validation_error",
                source=source,
                row=i,
                broker_exec_id=trade.broker_exec_id,
                error_count=len(errors),
            )
        else:
            result.valid.append(trade)

    return result

"""IBKR Flex Query ingester.

Two-step REST flow:
1. POST /FlexStatement.SendRequest → referenceCode
2. GET /FlexStatement.GetStatement (poll until ready) → XML report

Includes circuit breaker, exponential backoff, and idempotency check.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
import structlog
from lxml import etree
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.ingestion.base import BaseIngester
from backend.ingestion.normalizer import (
    ensure_utc,
    normalize_asset_class,
    normalize_side,
    safe_decimal,
    safe_str,
)
from backend.models.import_log import ImportLog
from backend.schemas.import_result import ImportResult
from backend.schemas.trade import NormalizedTrade

logger = structlog.get_logger(__name__)

FLEX_BASE_URL = "https://gdcdyn.interactivebrokers.com/Universal/servlet"
SEND_REQUEST_URL = f"{FLEX_BASE_URL}/FlexStatementService.SendRequest"
GET_STATEMENT_URL = f"{FLEX_BASE_URL}/FlexStatementService.GetStatement"

# IBKR asset class mapping
IBKR_ASSET_CLASS_MAP = {
    "STK": "stock",
    "FUT": "future",
    "OPT": "option",
    "CASH": "forex",
    "WAR": "stock",
    "BOND": "stock",
    "CFD": "stock",
}


class IBKRFlexIngester(BaseIngester):
    """Ingests trade data from IBKR Flex Web Service."""

    source = "flex_query"

    def __init__(
        self,
        flex_token: str | None = None,
        query_id: str | None = None,
        poll_interval: int | None = None,
        poll_max_attempts: int | None = None,
    ):
        self.flex_token = flex_token or settings.ibkr_flex_token
        self.query_id = query_id or settings.ibkr_query_id
        self.poll_interval = poll_interval or settings.ibkr_poll_interval_seconds
        self.poll_max_attempts = poll_max_attempts or settings.ibkr_poll_max_attempts

    def check_idempotency(self, db: Session | None = None) -> bool:
        """Check if we already have a successful import for today.

        Returns True if an import already succeeded today (skip).
        """
        own_session = db is None
        if own_session:
            db = SessionLocal()
        try:
            today_start = datetime.combine(date.today(), datetime.min.time()).replace(
                tzinfo=timezone.utc
            )
            stmt = select(ImportLog).where(
                ImportLog.source == self.source,
                ImportLog.status.in_(["success", "partial"]),
                ImportLog.started_at >= today_start,
            )
            result = db.execute(stmt).scalars().first()
            return result is not None
        finally:
            if own_session:
                db.close()

    def fetch_and_import(self, db: Session | None = None) -> ImportResult:
        """Full pipeline: check idempotency → fetch → normalize → import.

        Args:
            db: Optional database session.

        Returns:
            ImportResult with summary.
        """
        if self.check_idempotency(db):
            logger.info(
                "flex_query_skip_idempotent",
                message="Already imported today, skipping",
            )
            return ImportResult(
                import_log_id="00000000-0000-0000-0000-000000000000",
                source=self.source,
                status="skipped",
                records_total=0,
                records_imported=0,
                records_skipped_dup=0,
                records_failed=0,
            )

        if not self.flex_token or not self.query_id:
            raise ValueError(
                "IBKR Flex token and query ID must be configured. "
                "Set IBKR_FLEX_TOKEN and IBKR_QUERY_ID."
            )

        # Step 1: Request the report
        reference_code = self._send_request()

        # Step 2: Poll for the report
        xml_data = self._poll_for_report(reference_code)

        # Step 3: Parse XML and normalize
        trades = self._parse_flex_xml(xml_data)

        # Step 4: Import via base class
        return self.import_records(trades, db=db)

    def _send_request(self) -> str:
        """Step 1: Send the Flex Query request and get a reference code."""
        logger.info("flex_send_request", query_id=self.query_id)

        with httpx.Client(timeout=30) as client:
            response = client.post(
                SEND_REQUEST_URL,
                params={"t": self.flex_token, "q": self.query_id, "v": "3"},
            )
            response.raise_for_status()

        # Parse XML response
        root = etree.fromstring(response.content)
        status = root.findtext("Status")

        if status == "Success":
            ref_code = root.findtext("ReferenceCode")
            if not ref_code:
                raise RuntimeError("Flex SendRequest succeeded but no ReferenceCode")
            logger.info("flex_reference_code", reference_code=ref_code)
            return ref_code
        else:
            error_code = root.findtext("ErrorCode", "unknown")
            error_msg = root.findtext("ErrorMessage", "unknown")
            raise RuntimeError(
                f"Flex SendRequest failed: [{error_code}] {error_msg}"
            )

    def _poll_for_report(self, reference_code: str) -> bytes:
        """Step 2: Poll until the report is ready, with circuit breaker."""
        backoff = self.poll_interval

        for attempt in range(1, self.poll_max_attempts + 1):
            logger.debug(
                "flex_poll_attempt",
                attempt=attempt,
                reference_code=reference_code,
            )

            with httpx.Client(timeout=60) as client:
                try:
                    response = client.get(
                        GET_STATEMENT_URL,
                        params={
                            "t": self.flex_token,
                            "q": reference_code,
                            "v": "3",
                        },
                    )
                except httpx.TimeoutException:
                    logger.warning(
                        "flex_poll_timeout", attempt=attempt
                    )
                    time.sleep(min(backoff, 120))
                    backoff *= 2
                    continue

            # Check if it's XML (report ready or error)
            content_type = response.headers.get("content-type", "")

            if "text/xml" in content_type or "application/xml" in content_type:
                # Check if it's an error response or the actual report
                try:
                    root = etree.fromstring(response.content)
                    # Check if this is a status response (not ready yet)
                    status = root.findtext("Status")
                    if status and status != "Success":
                        error_code = root.findtext("ErrorCode", "")
                        # 1019 = "Statement generation in progress"
                        if error_code == "1019":
                            logger.debug(
                                "flex_not_ready",
                                attempt=attempt,
                                error_code=error_code,
                            )
                            time.sleep(self.poll_interval)
                            continue
                        else:
                            error_msg = root.findtext("ErrorMessage", "unknown")
                            raise RuntimeError(
                                f"Flex GetStatement error: [{error_code}] {error_msg}"
                            )
                except etree.XMLSyntaxError:
                    pass

                # If we got here with valid XML, it's the report
                return response.content

            # Non-XML response — might be transient error
            if response.status_code >= 500:
                logger.warning(
                    "flex_poll_server_error",
                    attempt=attempt,
                    status=response.status_code,
                )
                time.sleep(min(backoff, 120))
                backoff *= 2
                continue

            # 4xx = client error, stop immediately
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Flex GetStatement client error: HTTP {response.status_code}"
                )

            # Unknown success response
            return response.content

        raise RuntimeError(
            f"Flex Query polling timed out after {self.poll_max_attempts} attempts"
        )

    def _parse_flex_xml(self, xml_data: bytes) -> list[NormalizedTrade]:
        """Parse Flex Query XML and normalize to NormalizedTrade records."""
        root = etree.fromstring(xml_data)
        trades: list[NormalizedTrade] = []

        # Find all Trade elements (may be under FlexStatements/FlexStatement/Trades/Trade)
        trade_elements = root.xpath(".//Trade") or root.xpath(".//TradeConfirm")

        logger.info("flex_parse_trades", count=len(trade_elements))

        for elem in trade_elements:
            try:
                trade = self._normalize_flex_trade(elem)
                if trade:
                    trades.append(trade)
            except Exception as e:
                logger.error(
                    "flex_normalize_error",
                    error=str(e),
                    trade_id=elem.get("tradeID", "unknown"),
                )

        return trades

    def _normalize_flex_trade(self, elem: etree._Element) -> NormalizedTrade | None:
        """Normalize a single Flex Query XML trade element."""
        attrs = dict(elem.attrib)

        # Skip if no trade ID
        trade_id = safe_str(attrs.get("tradeID"))
        if not trade_id:
            return None

        # Parse executed_at — IBKR provides in exchange timezone
        date_time_str = safe_str(attrs.get("dateTime", attrs.get("tradeDate", "")))
        if not date_time_str:
            return None

        # Try various IBKR datetime formats
        executed_at = self._parse_ibkr_datetime(date_time_str)
        if executed_at is None:
            return None

        # Map asset class
        asset_category = safe_str(attrs.get("assetCategory", "STK"))
        asset_class = IBKR_ASSET_CLASS_MAP.get(asset_category, "stock")

        # Map side
        buy_sell = safe_str(attrs.get("buySell", ""))
        side = normalize_side(buy_sell)
        if side not in ("buy", "sell"):
            return None

        # Determine multiplier (contract multiplier for futures/options)
        multiplier_str = safe_str(attrs.get("multiplier", "1"))
        multiplier = safe_decimal(multiplier_str)
        if multiplier <= 0:
            multiplier = Decimal("1")

        return NormalizedTrade(
            broker="ibkr",
            broker_exec_id=trade_id,
            account_id=safe_str(attrs.get("accountId", "")),
            symbol=safe_str(attrs.get("symbol", "")),
            underlying=safe_str(attrs.get("underlyingSymbol")) or None,
            asset_class=asset_class,
            side=side,
            quantity=abs(safe_decimal(attrs.get("quantity", "0"))),
            price=safe_decimal(attrs.get("tradePrice", "0")),
            commission=abs(safe_decimal(attrs.get("ibCommission", "0"))),
            executed_at=executed_at,
            order_id=safe_str(attrs.get("ibOrderID")) or None,
            exchange=safe_str(attrs.get("exchange")) or None,
            currency=safe_str(attrs.get("currency", "USD")),
            multiplier=multiplier,
            raw_data=attrs,
        )

    @staticmethod
    def _parse_ibkr_datetime(dt_str: str) -> datetime | None:
        """Parse IBKR datetime strings in various formats."""
        formats = [
            "%Y%m%d;%H%M%S",  # 20250115;143000
            "%Y-%m-%d;%H:%M:%S",  # 2025-01-15;14:30:00
            "%Y-%m-%d, %H:%M:%S",  # 2025-01-15, 14:30:00
            "%Y-%m-%d %H:%M:%S",  # 2025-01-15 14:30:00
            "%Y%m%d",  # 20250115 (date only)
            "%Y-%m-%d",  # 2025-01-15 (date only)
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(dt_str.strip(), fmt)
                return ensure_utc(dt)
            except ValueError:
                continue

        return None

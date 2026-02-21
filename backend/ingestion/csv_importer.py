"""CSV importer with automatic format detection.

Supports:
- IBKR Activity Statement CSV
- Tradovate trade history CSV (Phase 2)
- Generic CSV with manual column mapping

Dedup hash for CSV includes source filename + row number to avoid
collisions on legitimate duplicate executions.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from zoneinfo import ZoneInfo

import structlog

from backend.config import settings
from backend.ingestion.base import BaseIngester
from backend.ingestion.normalizer import (
    ensure_utc,
    normalize_asset_class,
    normalize_side,
    safe_decimal,
    safe_str,
)
from backend.schemas.import_result import ImportResult
from backend.schemas.trade import NormalizedTrade

logger = structlog.get_logger(__name__)


class CSVFormat:
    """Detected CSV format identifiers."""

    IBKR = "ibkr"
    TRADOVATE = "tradovate"
    TRADOVATE_PERF = "tradovate_perf"
    UNKNOWN = "unknown"


class CSVImporter(BaseIngester):
    """Imports trades from CSV files with automatic format detection."""

    source = "csv"
    DEFAULT_IBKR_TIMEZONE = "America/New_York"
    DEFAULT_TRADOVATE_TIMEZONE = "Asia/Shanghai"

    def import_csv(
        self,
        file_content: bytes | str,
        filename: str = "upload.csv",
        db=None,
    ) -> ImportResult:
        """Import trades from a CSV file.

        Args:
            file_content: Raw CSV content (bytes or str).
            filename: Original filename (used in dedup hash).
            db: Optional database session.

        Returns:
            ImportResult with summary.
        """
        if isinstance(file_content, bytes):
            text = file_content.decode("utf-8-sig")  # Handle BOM
        else:
            text = file_content

        # Detect format
        fmt = self._detect_format(text)
        logger.info("csv_format_detected", format=fmt, filename=filename)

        # Parse based on format
        if fmt == CSVFormat.IBKR:
            trades = self._parse_ibkr_csv(text, filename)
        elif fmt == CSVFormat.TRADOVATE:
            trades = self._parse_tradovate_csv(text, filename)
        elif fmt == CSVFormat.TRADOVATE_PERF:
            trades = self._parse_tradovate_performance_csv(text, filename)
        else:
            raise ValueError(
                f"Unknown CSV format for file '{filename}'. "
                "Could not detect IBKR or Tradovate format from headers."
            )

        return self.import_records(trades, db=db)

    def _detect_format(self, text: str) -> str:
        """Detect the CSV format from header patterns.

        Returns CSVFormat constant.
        """
        lines = text.strip().split("\n")[:10]  # Check first 10 lines

        for line in lines:
            line_lower = line.lower()
            # IBKR Activity Statement has "Statement" section headers
            if "statement" in line_lower and "ibkr" in line_lower.replace("interactive brokers", "ibkr"):
                return CSVFormat.IBKR
            # Check for IBKR trade section
            if line_lower.startswith('"trades"') or line_lower.startswith("trades,"):
                return CSVFormat.IBKR
            # Check for typical IBKR trade headers
            if "tradeid" in line_lower or "ibcommission" in line_lower:
                return CSVFormat.IBKR
            # Tradovate CSV has distinctive columns
            if "execid" in line_lower and "contractname" in line_lower:
                return CSVFormat.TRADOVATE
            if "orderid" in line_lower and "b/s" in line_lower:
                return CSVFormat.TRADOVATE
            # Tradovate Performance report has buyFillId/sellFillId or buyPrice/sellPrice
            if "buyfillid" in line_lower and "sellfillid" in line_lower:
                return CSVFormat.TRADOVATE_PERF
            if "buyprice" in line_lower and "sellprice" in line_lower and "boughttimestamp" in line_lower:
                return CSVFormat.TRADOVATE_PERF

        # Try to detect from column headers
        reader = csv.reader(io.StringIO(text))
        for row in reader:
            header_str = ",".join(row).lower()
            if "tradeid" in header_str or "ibcommission" in header_str:
                return CSVFormat.IBKR
            if "execid" in header_str or "contractname" in header_str:
                return CSVFormat.TRADOVATE
            if "buyfillid" in header_str and "sellfillid" in header_str:
                return CSVFormat.TRADOVATE_PERF
            if "buyprice" in header_str and "sellprice" in header_str and "boughttimestamp" in header_str:
                return CSVFormat.TRADOVATE_PERF
            break  # Only check first row

        return CSVFormat.UNKNOWN

    def _parse_rows(
        self,
        text: str,
        filename: str,
        normalize_fn,
        *,
        log_event: str,
        error_event: str,
    ) -> list[NormalizedTrade]:
        """Shared DictReader parse loop for CSV formats.

        Iterates rows from a ``csv.DictReader``, calls *normalize_fn* for each
        row, collects results, and logs parse errors per row.

        *normalize_fn* signature: ``(record, filename, row_number) -> NormalizedTrade | list[NormalizedTrade] | None``

        Args:
            text: Raw CSV text.
            filename: Original filename (for logging and dedup hashing).
            normalize_fn: Row normalizer callable.
            log_event: Structured log event name on successful parse.
            error_event: Structured log event name on per-row errors.

        Returns:
            Flat list of ``NormalizedTrade`` objects.
        """
        trades: list[NormalizedTrade] = []
        reader = csv.DictReader(io.StringIO(text))
        row_number = 0

        for row in reader:
            row_number += 1
            try:
                result = normalize_fn(row, filename, row_number)
                if result is None:
                    continue
                if isinstance(result, list):
                    trades.extend(result)
                else:
                    trades.append(result)
            except Exception as e:
                logger.warning(
                    error_event,
                    filename=filename,
                    row=row_number,
                    error=str(e),
                )

        logger.info(log_event, filename=filename, trade_count=len(trades))
        return trades

    def _parse_ibkr_csv(self, text: str, filename: str) -> list[NormalizedTrade]:
        """Parse IBKR Activity Statement CSV.

        IBKR CSVs have multiple sections. We look for the "Trades" section
        and parse the "Data" rows within it.
        """
        trades: list[NormalizedTrade] = []
        reader = csv.reader(io.StringIO(text))
        in_trades_section = False
        headers: list[str] | None = None
        row_number = 0
        account_id = ""

        for row in reader:
            if not row:
                continue

            # Detect section boundaries
            section = row[0].strip() if row else ""
            record_type = row[1].strip() if len(row) > 1 else ""

            # Capture statement-level account ID for downstream rows
            if section == "Statement" and len(row) > 3:
                if record_type == "Data" and safe_str(row[2]).lower() == "accountid":
                    account_id = safe_str(row[3])

            if section != "Trades":
                if in_trades_section and section:
                    in_trades_section = False
                    headers = None
                continue

            in_trades_section = True

            # Parse header row
            if record_type == "Header":
                headers = [h.strip() for h in row[2:]]
                continue

            # Parse data rows
            if record_type == "Data" and headers:
                data = row[2:]
                if len(data) < len(headers):
                    data.extend([""] * (len(headers) - len(data)))

                record = dict(zip(headers, data))
                row_number += 1

                try:
                    trade = self._normalize_ibkr_csv_row(
                        record, filename, row_number, account_id=account_id
                    )
                    if trade:
                        trades.append(trade)
                except Exception as e:
                    logger.warning(
                        "ibkr_csv_parse_error",
                        filename=filename,
                        row=row_number,
                        error=str(e),
                    )

        logger.info(
            "ibkr_csv_parsed", filename=filename, trade_count=len(trades)
        )
        return trades

    def _normalize_ibkr_csv_row(
        self,
        record: dict,
        filename: str,
        row_number: int,
        account_id: str = "",
    ) -> NormalizedTrade | None:
        """Normalize a single IBKR CSV data row."""
        symbol = safe_str(record.get("Symbol", ""))
        if not symbol:
            return None

        # Generate broker_exec_id from CSV content hash
        trade_id = safe_str(record.get("TradeID", ""))
        if trade_id:
            broker_exec_id = trade_id
        else:
            # Fallback: hash of key fields + filename + row
            hash_input = (
                f"{filename}|{row_number}|{symbol}|"
                f"{record.get('Buy/Sell', '')}|{record.get('Quantity', '')}|"
                f"{record.get('T. Price', record.get('TradePrice', ''))}|"
                f"{record.get('Date/Time', record.get('DateTime', ''))}"
            )
            broker_exec_id = hashlib.sha256(hash_input.encode()).hexdigest()

        # Parse side
        side_raw = safe_str(record.get("Buy/Sell", record.get("Code", "")))
        side = normalize_side(side_raw)
        quantity_raw = safe_decimal(record.get("Quantity", "0"))
        if side not in ("buy", "sell"):
            # Some IBKR Activity CSV variants omit Buy/Sell; infer from quantity sign.
            if quantity_raw > 0:
                side = "buy"
            elif quantity_raw < 0:
                side = "sell"
            else:
                return None

        # Parse datetime
        dt_str = safe_str(
            record.get("Date/Time", record.get("DateTime", record.get("TradeDate", "")))
        )
        executed_at = self._parse_ibkr_csv_datetime(dt_str)
        if executed_at is None:
            return None

        # Parse asset class
        asset_class_raw = safe_str(record.get("Asset Category", record.get("AssetClass", "STK")))
        asset_class = normalize_asset_class(asset_class_raw)

        return NormalizedTrade(
            broker="ibkr",
            broker_exec_id=broker_exec_id,
            account_id=safe_str(record.get("Account", "")) or account_id,
            symbol=symbol,
            underlying=safe_str(record.get("Underlying Symbol")) or None,
            asset_class=asset_class,
            side=side,
            quantity=abs(quantity_raw),
            price=safe_decimal(
                record.get("T. Price", record.get("TradePrice", "0"))
            ),
            commission=abs(
                safe_decimal(
                    record.get("Comm/Fee", record.get("IBCommission", "0"))
                )
            ),
            executed_at=executed_at,
            order_id=safe_str(record.get("Order ID", record.get("IBOrderID"))) or None,
            exchange=safe_str(record.get("Exchange")) or None,
            currency=safe_str(record.get("Currency", "USD")),
            raw_data=record,
        )

    @staticmethod
    @lru_cache(maxsize=16)
    def _zoneinfo(tz_name: str) -> ZoneInfo:
        """Load and cache ZoneInfo instances."""
        return ZoneInfo(tz_name)

    @classmethod
    def _resolve_timezone(
        cls,
        configured_tz: str | None,
        *,
        fallback_tz: str,
        setting_name: str,
    ) -> ZoneInfo:
        """Resolve a configured timezone string with fallback and warning."""
        candidate = (configured_tz or "").strip() or fallback_tz
        try:
            return cls._zoneinfo(candidate)
        except Exception:
            logger.warning(
                "csv_timezone_fallback",
                setting_name=setting_name,
                configured_value=candidate,
                fallback=fallback_tz,
            )
            return cls._zoneinfo(fallback_tz)

    @staticmethod
    def _parse_explicit_offset_datetime(dt_str: str) -> datetime | None:
        """Parse ISO-like datetime strings that already include UTC offset."""
        value = dt_str.strip()
        if not value:
            return None

        # Normalize trailing Z for datetime.fromisoformat support.
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            return None
        return ensure_utc(parsed)

    @classmethod
    def _parse_datetime_with_default_timezone(
        cls,
        dt_str: str,
        *,
        formats: list[str],
        default_tz: ZoneInfo,
    ) -> datetime | None:
        """Parse datetime and convert to UTC.

        Rule:
        - If timestamp carries an explicit offset/Z, honor it directly.
        - Otherwise, treat it as source-local time (*default_tz*) then convert to UTC.
        """
        if not dt_str:
            return None

        value = dt_str.strip()
        if not value:
            return None

        # 1) Explicit-offset strings (e.g. 2025-01-01T10:00:00Z / +08:00)
        explicit = cls._parse_explicit_offset_datetime(value)
        if explicit is not None:
            return explicit

        # 2) Common timezone suffixes that are not reliably handled by strptime.
        no_suffix = re.sub(
            r"\s+(UTC|GMT|EST|EDT|ET)$",
            "",
            value,
            flags=re.IGNORECASE,
        )
        candidates = [value]
        if no_suffix != value:
            candidates.append(no_suffix)

        for candidate in candidates:
            for fmt in formats:
                try:
                    parsed = datetime.strptime(candidate, fmt)
                except ValueError:
                    continue
                if parsed.tzinfo is not None:
                    return ensure_utc(parsed)
                return parsed.replace(tzinfo=default_tz).astimezone(timezone.utc)

        return None

    @classmethod
    def _parse_ibkr_csv_datetime(
        cls,
        dt_str: str,
        source_timezone: str | None = None,
    ) -> datetime | None:
        """Parse IBKR CSV datetime values and normalize to UTC.

        IBKR Activity CSV timestamps are ET by default.
        """
        source_tz = cls._resolve_timezone(
            source_timezone or getattr(settings, "ibkr_csv_timezone", None),
            fallback_tz=cls.DEFAULT_IBKR_TIMEZONE,
            setting_name="ibkr_csv_timezone",
        )
        formats = [
            "%Y-%m-%d, %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y%m%d;%H%M%S",
            "%Y%m%d",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y",
        ]
        return cls._parse_datetime_with_default_timezone(
            dt_str,
            formats=formats,
            default_tz=source_tz,
        )

    def _parse_tradovate_csv(
        self, text: str, filename: str
    ) -> list[NormalizedTrade]:
        """Parse Tradovate trade history CSV export.

        Tradovate CSVs typically have columns like:
        orderId, execId, contractName, b/s, qty, price, ...
        """
        return self._parse_rows(
            text, filename,
            self._normalize_tradovate_csv_row,
            log_event="tradovate_csv_parsed",
            error_event="tradovate_csv_parse_error",
        )

    def _normalize_tradovate_csv_row(
        self, record: dict, filename: str, row_number: int
    ) -> NormalizedTrade | None:
        """Normalize a single Tradovate CSV row."""
        # Normalize header keys (strip whitespace)
        record = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in record.items()}

        # Get contract/symbol name
        symbol = safe_str(
            record.get("contractName", record.get("Contract", record.get("Symbol", "")))
        )
        if not symbol:
            return None

        # Generate broker_exec_id
        exec_id = safe_str(record.get("execId", record.get("ExecId", "")))
        if exec_id:
            broker_exec_id = exec_id
        else:
            # Fallback: hash of key fields + filename + row
            hash_input = (
                f"{filename}|{row_number}|{symbol}|"
                f"{record.get('b/s', record.get('B/S', ''))}|"
                f"{record.get('qty', record.get('Qty', ''))}|"
                f"{record.get('price', record.get('Price', ''))}|"
                f"{record.get('time', record.get('Time', record.get('Date/Time', '')))}"
            )
            broker_exec_id = hashlib.sha256(hash_input.encode()).hexdigest()

        # Parse side
        side_raw = safe_str(
            record.get("b/s", record.get("B/S", record.get("Side", "")))
        )
        side = normalize_side(side_raw)
        if side not in ("buy", "sell"):
            return None

        # Parse datetime
        dt_str = safe_str(
            record.get("time", record.get("Time", record.get("Date/Time",
            record.get("fillTime", ""))))
        )
        executed_at = self._parse_tradovate_csv_datetime(dt_str)
        if executed_at is None:
            return None

        # Parse account
        account_id = safe_str(
            record.get("accountId", record.get("Account", ""))
        )

        return NormalizedTrade(
            broker="tradovate",
            broker_exec_id=broker_exec_id,
            account_id=account_id,
            symbol=symbol,
            underlying=None,
            asset_class="future",  # Tradovate is futures-only
            side=side,
            quantity=abs(safe_decimal(record.get("qty", record.get("Qty", "0")))),
            price=safe_decimal(record.get("price", record.get("Price", "0"))),
            commission=abs(
                safe_decimal(
                    record.get("commission", record.get("Commission", "0"))
                )
            ),
            executed_at=executed_at,
            order_id=safe_str(record.get("orderId", record.get("OrderId"))) or None,
            exchange="TRADOVATE",
            currency="USD",
            raw_data=record,
        )

    def _parse_tradovate_performance_csv(
        self, text: str, filename: str
    ) -> list[NormalizedTrade]:
        """Parse Tradovate Performance report CSV export.

        Tradovate Performance CSVs contain paired trades with columns like:
        symbol, _priceFormat, _priceFormatType, _tickSize, buyFillId, sellFillId,
        qty, buyPrice, sellPrice, pnl, boughtTimestamp, soldTimestamp, duration

        Each row represents a completed round-trip trade. We split it into
        two NormalizedTrade records (buy + sell).
        """
        trades = self._parse_rows(
            text, filename,
            self._normalize_tradovate_perf_row,
            log_event="tradovate_perf_csv_parsed",
            error_event="tradovate_perf_csv_parse_error",
        )

        # 第二轮：对 multiplier 为 1（无法从 price_diff 推断）的 trade，
        # 从同 symbol 的其他行继承 multiplier
        symbol_multiplier: dict[str, Decimal] = {}
        for t in trades:
            if t.multiplier != Decimal("1"):
                symbol_multiplier[t.symbol] = t.multiplier
        for t in trades:
            if t.multiplier == Decimal("1") and t.symbol in symbol_multiplier:
                t.multiplier = symbol_multiplier[t.symbol]

        return trades

    def _normalize_tradovate_perf_row(
        self, record: dict, filename: str, row_number: int
    ) -> list[NormalizedTrade]:
        """Normalize a single Tradovate Performance CSV row into buy + sell trades."""
        # 去除 header key 的空白
        record = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in record.items()}

        symbol = safe_str(record.get("symbol", ""))
        if not symbol:
            return []

        qty = abs(safe_decimal(record.get("qty", "0")))
        if qty == 0:
            return []

        buy_price = safe_decimal(record.get("buyPrice", "0"))
        sell_price = safe_decimal(record.get("sellPrice", "0"))

        bought_ts = safe_str(record.get("boughtTimestamp", ""))
        sold_ts = safe_str(record.get("soldTimestamp", ""))

        buy_fill_id = safe_str(record.get("buyFillId", ""))
        sell_fill_id = safe_str(record.get("sellFillId", ""))

        # 从 CSV 的 pnl 字段和价格差反推合约乘数（point_value）
        # pnl 格式: "$62.50" 或 "$(41.25)"
        pnl_str = safe_str(record.get("pnl", ""))
        pnl_value = self._parse_tradovate_pnl(pnl_str)
        price_diff = sell_price - buy_price
        if price_diff != 0 and qty > 0 and pnl_value is not None:
            multiplier = abs(pnl_value / (price_diff * qty))
        else:
            # 无法推断时默认为 1
            multiplier = Decimal("1")

        results: list[NormalizedTrade] = []

        # 解析买入时间
        buy_dt = self._parse_tradovate_csv_datetime(bought_ts)
        if buy_dt:
            # 使用 fillId + row_number 避免同一 fillId 出现在多行时重复
            if buy_fill_id:
                buy_exec_id = f"{buy_fill_id}_r{row_number}_buy"
            else:
                buy_exec_id = hashlib.sha256(
                    f"{filename}|{row_number}|{symbol}|buy|{qty}|{buy_price}|{bought_ts}".encode()
                ).hexdigest()
            results.append(NormalizedTrade(
                broker="tradovate",
                broker_exec_id=buy_exec_id,
                account_id="",
                symbol=symbol,
                underlying=None,
                asset_class="future",
                side="buy",
                quantity=qty,
                price=buy_price,
                commission=Decimal("0"),
                executed_at=buy_dt,
                order_id=None,
                exchange="TRADOVATE",
                currency="USD",
                multiplier=multiplier,
                raw_data=record,
            ))

        # 解析卖出时间
        sell_dt = self._parse_tradovate_csv_datetime(sold_ts)
        if sell_dt:
            # 使用 fillId + row_number 避免同一 fillId 出现在多行时重复
            if sell_fill_id:
                sell_exec_id = f"{sell_fill_id}_r{row_number}_sell"
            else:
                sell_exec_id = hashlib.sha256(
                    f"{filename}|{row_number}|{symbol}|sell|{qty}|{sell_price}|{sold_ts}".encode()
                ).hexdigest()
            results.append(NormalizedTrade(
                broker="tradovate",
                broker_exec_id=sell_exec_id,
                account_id="",
                symbol=symbol,
                underlying=None,
                asset_class="future",
                side="sell",
                quantity=qty,
                price=sell_price,
                commission=Decimal("0"),
                executed_at=sell_dt,
                order_id=None,
                exchange="TRADOVATE",
                currency="USD",
                multiplier=multiplier,
                raw_data=record,
            ))

        return results

    @staticmethod
    def _parse_tradovate_pnl(pnl_str: str) -> Decimal | None:
        """解析 Tradovate Performance CSV 的 pnl 字段。

        格式: "$62.50" (正), "$(41.25)" (负), "$0.00"
        """
        if not pnl_str:
            return None
        s = pnl_str.strip()
        negative = False
        if "$(" in s and s.endswith(")"):
            negative = True
            s = s.replace("$(", "").replace(")", "")
        else:
            s = s.replace("$", "")
        s = s.replace(",", "")
        try:
            val = Decimal(s)
            return -val if negative else val
        except Exception:
            return None

    @classmethod
    def _parse_tradovate_csv_datetime(
        cls,
        dt_str: str,
        source_timezone: str | None = None,
    ) -> datetime | None:
        """Parse Tradovate CSV datetime values and normalize to UTC.

        Tradovate export timestamps are local to the exporting environment.
        """
        source_tz = cls._resolve_timezone(
            source_timezone or getattr(settings, "tradovate_csv_timezone", None),
            fallback_tz=cls.DEFAULT_TRADOVATE_TIMEZONE,
            setting_name="tradovate_csv_timezone",
        )
        formats = [
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %I:%M:%S %p",
        ]
        return cls._parse_datetime_with_default_timezone(
            dt_str,
            formats=formats,
            default_tz=source_tz,
        )

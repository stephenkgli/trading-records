"""
Tests for Tradovate Performance CSV import.

Tests cover:
1. Format detection — correctly identifies Tradovate Performance CSV
2. Parsing correctness — row-level field extraction
3. Duplicate fillId handling — same buyFillId/sellFillId across multiple rows
4. Datetime parsing — Tradovate Performance timestamp format
5. Edge cases — zero pnl, different symbols
6. Database import — end-to-end import with db_session

Reference: Performance.csv real data from Tradovate
"""

from datetime import timezone
from decimal import Decimal

import pytest

from backend.ingestion.csv_importer import CSVImporter, CSVFormat


# ===========================================================================
# Format Detection
# ===========================================================================

class TestTradovatePerfFormatDetection:
    """Test automatic detection of Tradovate Performance CSV format."""

    @pytest.fixture
    def importer(self):
        return CSVImporter()

    def test_detect_tradovate_perf_format(self, importer, tradovate_performance_csv):
        """Tradovate Performance CSV should be detected as 'tradovate_perf'."""
        detected = importer._detect_format(tradovate_performance_csv)
        assert detected == CSVFormat.TRADOVATE_PERF

    def test_detect_tradovate_perf_from_header_only(self, importer):
        """Detection should work from header row alone."""
        header = "symbol,_priceFormat,_priceFormatType,_tickSize,buyFillId,sellFillId,qty,buyPrice,sellPrice,pnl,boughtTimestamp,soldTimestamp,duration\n"
        detected = importer._detect_format(header)
        assert detected == CSVFormat.TRADOVATE_PERF

    def test_not_confused_with_tradovate_export(self, importer, tradovate_export_csv):
        """Tradovate export CSV should NOT be detected as 'tradovate_perf'."""
        detected = importer._detect_format(tradovate_export_csv)
        assert detected == CSVFormat.TRADOVATE
        assert detected != CSVFormat.TRADOVATE_PERF


# ===========================================================================
# Parsing
# ===========================================================================

class TestTradovatePerfParsing:
    """Test the Tradovate Performance CSV row-level parsing logic."""

    @pytest.fixture
    def importer(self):
        return CSVImporter()

    def test_parse_returns_trades(self, importer, tradovate_performance_csv):
        """_parse_tradovate_performance_csv should return NormalizedTrade list."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        assert len(trades) > 0
        for trade in trades:
            assert trade.broker == "tradovate"
            assert trade.symbol is not None
            assert trade.asset_class == "future"

    def test_each_row_produces_two_trades(self, importer, tradovate_performance_csv):
        """Each Performance CSV row should produce exactly 2 trades (buy + sell)."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        # fixture 有 10 行数据，应产生 20 条交易
        assert len(trades) == 20

    def test_buy_and_sell_sides(self, importer, tradovate_performance_csv):
        """Trades should alternate between buy and sell for each row pair."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        buy_count = sum(1 for t in trades if t.side == "buy")
        sell_count = sum(1 for t in trades if t.side == "sell")
        assert buy_count == 10
        assert sell_count == 10

    def test_first_row_buy_price(self, importer, tradovate_performance_csv):
        """First row buy price should be 6117.75."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        # 第一行的 buy trade
        first_buy = trades[0]
        assert first_buy.side == "buy"
        assert first_buy.price == Decimal("6117.75")
        assert first_buy.symbol == "MESH5"

    def test_first_row_sell_price(self, importer, tradovate_performance_csv):
        """First row sell price should be 6130.25."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        first_sell = trades[1]
        assert first_sell.side == "sell"
        assert first_sell.price == Decimal("6130.25")

    def test_datetime_parsing(self, importer, tradovate_performance_csv):
        """Timestamps should be correctly parsed from MM/DD/YYYY HH:MM:SS format."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        # 第一行: boughtTimestamp = 01/22/2025 23:02:03
        first_buy = trades[0]
        assert first_buy.executed_at.year == 2025
        assert first_buy.executed_at.month == 1
        assert first_buy.executed_at.day == 22
        assert first_buy.executed_at.hour == 23
        assert first_buy.executed_at.minute == 2
        assert first_buy.executed_at.second == 3

    def test_quantity_parsed_correctly(self, importer, tradovate_performance_csv):
        """Quantity should be 1 for all rows in fixture."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        for trade in trades:
            assert trade.quantity == Decimal("1")

    def test_multiple_symbols(self, importer, tradovate_performance_csv):
        """Fixture contains MESH5, MESM5, and MESU5 symbols."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        symbols = {t.symbol for t in trades}
        assert "MESH5" in symbols
        assert "MESM5" in symbols
        assert "MESU5" in symbols

    def test_zero_pnl_row_still_parsed(self, importer, tradovate_performance_csv):
        """Row with $0.00 pnl should still produce buy + sell trades."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        # 第 3 行（index 2）: pnl = $0.00, buyPrice = sellPrice = 6101.25
        # buy 在 index 4, sell 在 index 5
        zero_pnl_buy = [t for t in trades if t.price == Decimal("6101.25") and t.side == "buy"]
        zero_pnl_sell = [t for t in trades if t.price == Decimal("6101.25") and t.side == "sell"]
        assert len(zero_pnl_buy) == 1
        assert len(zero_pnl_sell) == 1


# ===========================================================================
# Duplicate FillId Handling
# ===========================================================================

class TestDuplicateFillIdHandling:
    """Test that duplicate buyFillId/sellFillId in different rows are handled correctly."""

    @pytest.fixture
    def importer(self):
        return CSVImporter()

    def test_duplicate_buy_fill_id_unique_exec_ids(self, importer, tradovate_performance_csv):
        """Same buyFillId across multiple rows should produce unique broker_exec_ids."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        # buyFillId 6008479906 出现在第 4 和第 5 行
        buy_trades_with_same_fill = [
            t for t in trades
            if t.side == "buy" and "6008479906" in t.broker_exec_id
        ]
        assert len(buy_trades_with_same_fill) == 2
        # 确保它们的 broker_exec_id 不同
        exec_ids = [t.broker_exec_id for t in buy_trades_with_same_fill]
        assert len(set(exec_ids)) == 2, f"Expected unique exec_ids, got: {exec_ids}"

    def test_duplicate_sell_fill_id_unique_exec_ids(self, importer, tradovate_performance_csv):
        """Same sellFillId across multiple rows should produce unique broker_exec_ids."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        # sellFillId 6008481385 出现在第 6、7、8 行
        sell_trades_with_same_fill = [
            t for t in trades
            if t.side == "sell" and "6008481385" in t.broker_exec_id
        ]
        assert len(sell_trades_with_same_fill) == 3
        exec_ids = [t.broker_exec_id for t in sell_trades_with_same_fill]
        assert len(set(exec_ids)) == 3, f"Expected unique exec_ids, got: {exec_ids}"

    def test_all_exec_ids_unique(self, importer, tradovate_performance_csv):
        """All broker_exec_ids across all parsed trades must be unique."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        exec_ids = [t.broker_exec_id for t in trades]
        assert len(exec_ids) == len(set(exec_ids)), (
            f"Found duplicate exec_ids: {[x for x in exec_ids if exec_ids.count(x) > 1]}"
        )


# ===========================================================================
# Datetime Parsing
# ===========================================================================

class TestTradovatePerfDatetime:
    """Test datetime parsing for Tradovate Performance timestamps."""

    def test_parse_standard_format(self):
        """Standard Tradovate Performance datetime format should parse."""
        dt = CSVImporter._parse_tradovate_csv_datetime("01/22/2025 23:02:03")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 22
        assert dt.hour == 23
        assert dt.minute == 2
        assert dt.second == 3

    def test_parse_empty_string(self):
        """Empty string should return None."""
        dt = CSVImporter._parse_tradovate_csv_datetime("")
        assert dt is None

    def test_parsed_datetime_has_utc(self):
        """Parsed datetime should have UTC timezone."""
        dt = CSVImporter._parse_tradovate_csv_datetime("06/16/2025 21:57:36")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.tzinfo == timezone.utc


# ===========================================================================
# Database Import (Integration)
# ===========================================================================

class TestTradovatePerfImport:
    """Test end-to-end import of Tradovate Performance CSV into database."""

    def test_import_happy_path(self, db_session, tradovate_performance_csv):
        """Import valid Tradovate Performance CSV should succeed."""
        importer = CSVImporter()
        result = importer.import_csv(
            file_content=tradovate_performance_csv,
            filename="Performance.csv",
            db=db_session,
        )
        assert result is not None
        assert result.status == "success"
        assert result.records_imported > 0

    def test_import_correct_count(self, db_session, tradovate_performance_csv):
        """Should import 20 trades (10 rows × 2 trades per row)."""
        importer = CSVImporter()
        result = importer.import_csv(
            file_content=tradovate_performance_csv,
            filename="Performance.csv",
            db=db_session,
        )
        assert result.records_total == 20
        assert result.records_imported == 20

    def test_import_source_is_csv(self, db_session, tradovate_performance_csv):
        """Import result source should be 'csv'."""
        importer = CSVImporter()
        result = importer.import_csv(
            file_content=tradovate_performance_csv,
            filename="Performance.csv",
            db=db_session,
        )
        assert result.source == "csv"

    def test_import_no_duplicates_on_reimport(self, db_session, tradovate_performance_csv):
        """Re-importing the same file should skip all records as duplicates."""
        importer = CSVImporter()
        result1 = importer.import_csv(
            file_content=tradovate_performance_csv,
            filename="Performance.csv",
            db=db_session,
        )
        assert result1.records_imported == 20

        result2 = importer.import_csv(
            file_content=tradovate_performance_csv,
            filename="Performance.csv",
            db=db_session,
        )
        assert result2.records_imported == 0
        assert result2.records_skipped_dup == 20

    def test_import_with_bytes_input(self, db_session, tradovate_performance_csv):
        """Import should work with bytes input (as received from file upload)."""
        importer = CSVImporter()
        result = importer.import_csv(
            file_content=tradovate_performance_csv.encode("utf-8"),
            filename="Performance.csv",
            db=db_session,
        )
        assert result.status == "success"
        assert result.records_imported == 20

    def test_import_windows_line_endings(self, db_session):
        """CSV with Windows \\r\\n line endings should parse correctly."""
        csv_data = (
            "symbol,_priceFormat,_priceFormatType,_tickSize,buyFillId,sellFillId,"
            "qty,buyPrice,sellPrice,pnl,boughtTimestamp,soldTimestamp,duration\r\n"
            "MESH5,-2,0,0.25,9999990001,9999990002,1,6117.75,6130.25,$62.50,"
            "01/22/2025 23:02:03,01/23/2025 00:30:16,1h 28min 12sec\r\n"
        )
        importer = CSVImporter()
        result = importer.import_csv(
            file_content=csv_data,
            filename="test_crlf.csv",
            db=db_session,
        )
        assert result.status == "success"
        assert result.records_imported == 2  # buy + sell


# ===========================================================================
# Edge Cases
# ===========================================================================

class TestTradovatePerfEdgeCases:
    """Test edge cases for Tradovate Performance CSV parsing."""

    @pytest.fixture
    def importer(self):
        return CSVImporter()

    def test_empty_performance_csv(self, importer):
        """Performance CSV with only header should return empty list."""
        csv_data = "symbol,_priceFormat,_priceFormatType,_tickSize,buyFillId,sellFillId,qty,buyPrice,sellPrice,pnl,boughtTimestamp,soldTimestamp,duration\n"
        trades = importer._parse_tradovate_performance_csv(csv_data, "empty.csv")
        assert len(trades) == 0

    def test_missing_symbol_skipped(self, importer):
        """Row with empty symbol should be skipped."""
        csv_data = (
            "symbol,_priceFormat,_priceFormatType,_tickSize,buyFillId,sellFillId,"
            "qty,buyPrice,sellPrice,pnl,boughtTimestamp,soldTimestamp,duration\n"
            ",-2,0,0.25,100,200,1,100.00,110.00,$10.00,"
            "01/22/2025 23:02:03,01/23/2025 00:30:16,1h\n"
        )
        trades = importer._parse_tradovate_performance_csv(csv_data, "test.csv")
        assert len(trades) == 0

    def test_zero_quantity_skipped(self, importer):
        """Row with qty=0 should be skipped."""
        csv_data = (
            "symbol,_priceFormat,_priceFormatType,_tickSize,buyFillId,sellFillId,"
            "qty,buyPrice,sellPrice,pnl,boughtTimestamp,soldTimestamp,duration\n"
            "MESH5,-2,0,0.25,100,200,0,100.00,110.00,$10.00,"
            "01/22/2025 23:02:03,01/23/2025 00:30:16,1h\n"
        )
        trades = importer._parse_tradovate_performance_csv(csv_data, "test.csv")
        assert len(trades) == 0

    def test_commission_defaults_to_zero(self, importer, tradovate_performance_csv):
        """Performance CSV has no commission column, so commission should be 0."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        for trade in trades:
            assert trade.commission == Decimal("0")

    def test_exchange_is_tradovate(self, importer, tradovate_performance_csv):
        """All trades should have exchange='TRADOVATE'."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        for trade in trades:
            assert trade.exchange == "TRADOVATE"

    def test_currency_is_usd(self, importer, tradovate_performance_csv):
        """All trades should have currency='USD'."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        for trade in trades:
            assert trade.currency == "USD"

    def test_account_id_is_empty_string(self, importer, tradovate_performance_csv):
        """Performance CSV has no account info, account_id should be empty."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        for trade in trades:
            assert trade.account_id == ""

    def test_raw_data_contains_original_fields(self, importer, tradovate_performance_csv):
        """raw_data should contain the original CSV fields."""
        trades = importer._parse_tradovate_performance_csv(
            tradovate_performance_csv, "Performance.csv"
        )
        first_trade = trades[0]
        assert "buyFillId" in first_trade.raw_data
        assert "sellFillId" in first_trade.raw_data
        assert "pnl" in first_trade.raw_data

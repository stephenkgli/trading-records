"""
Integration tests for the CSV importer.

Tests:
1. IBKR format detection — correctly identifies IBKR Activity Statement CSV
2. Tradovate format detection — correctly identifies Tradovate export CSV
3. Unknown format — gracefully handles unrecognized CSV formats
4. Empty file — handles empty CSV files
5. IBKR CSV import with database

Reference: design-doc-final.md Section 5.5
"""

import pytest

from backend.ingestion.csv_importer import CSVImporter, CSVFormat


# ===========================================================================
# Format Detection
# ===========================================================================

class TestCSVFormatDetection:
    """Test automatic detection of CSV broker format."""

    @pytest.fixture
    def importer(self):
        return CSVImporter()

    def test_detect_ibkr_format(self, importer, ibkr_activity_csv):
        """IBKR Activity Statement CSV should be detected as 'ibkr'."""
        detected = importer._detect_format(ibkr_activity_csv)
        assert detected == CSVFormat.IBKR

    def test_detect_ibkr_no_trades(self, importer, ibkr_activity_no_trades_csv):
        """IBKR CSV with no trades should still be detected as 'ibkr'."""
        detected = importer._detect_format(ibkr_activity_no_trades_csv)
        assert detected == CSVFormat.IBKR

    def test_detect_tradovate_format(self, importer, tradovate_export_csv):
        """Tradovate export CSV should be detected as 'tradovate'."""
        detected = importer._detect_format(tradovate_export_csv)
        assert detected == CSVFormat.TRADOVATE

    def test_detect_unknown_format(self, importer):
        """An unrecognized CSV format should return 'unknown'."""
        csv_data = "col1,col2,col3\nval1,val2,val3\n"
        detected = importer._detect_format(csv_data)
        assert detected == CSVFormat.UNKNOWN


# ===========================================================================
# IBKR CSV Import
# ===========================================================================

class TestIBKRCSVImport:
    """Test importing IBKR Activity Statement CSV files."""

    def test_ibkr_csv_import_happy_path(self, db_session, ibkr_activity_csv):
        """Import valid IBKR CSV should succeed with correct record count."""
        importer = CSVImporter()
        result = importer.import_csv(
            file_content=ibkr_activity_csv,
            filename="ibkr_activity.csv",
            db=db_session,
        )

        assert result is not None
        assert result.records_imported > 0
        assert result.status == "success"

    def test_ibkr_csv_correct_count(self, db_session, ibkr_activity_csv):
        """Should import the trade data rows (excluding headers/totals/subtotals)."""
        importer = CSVImporter()
        result = importer.import_csv(
            file_content=ibkr_activity_csv,
            filename="ibkr_activity.csv",
            db=db_session,
        )

        # 5 data rows in the fixture (AAPL buy, AAPL sell, MSFT buy, option, future)
        assert result.records_total == 5

    def test_ibkr_csv_no_trades(self, db_session, ibkr_activity_no_trades_csv):
        """IBKR CSV with no trade rows should import 0 records."""
        importer = CSVImporter()
        result = importer.import_csv(
            file_content=ibkr_activity_no_trades_csv,
            filename="ibkr_no_trades.csv",
            db=db_session,
        )

        assert result.records_total == 0
        assert result.records_imported == 0
        assert result.status == "success"

    def test_ibkr_csv_source_is_csv(self, db_session, ibkr_activity_csv):
        """Import result source should be 'csv'."""
        importer = CSVImporter()
        result = importer.import_csv(
            file_content=ibkr_activity_csv,
            filename="ibkr_activity.csv",
            db=db_session,
        )
        assert result.source == "csv"


# ===========================================================================
# Unknown Format
# ===========================================================================

class TestUnknownCSVFormat:
    """Test handling of unrecognized CSV formats."""

    def test_unknown_format_raises_error(self, db_session):
        """Importing an unrecognized CSV format should raise ValueError."""
        csv_data = "date,ticker,amount\n2025-01-15,AAPL,100\n"
        importer = CSVImporter()

        with pytest.raises(ValueError, match="Unknown CSV format"):
            importer.import_csv(
                file_content=csv_data,
                filename="unknown.csv",
                db=db_session,
            )


# ===========================================================================
# IBKR CSV Parsing
# ===========================================================================

class TestIBKRCSVParsing:
    """Test the IBKR CSV row-level parsing logic."""

    def test_parse_ibkr_csv_returns_trades(self, ibkr_activity_csv):
        """_parse_ibkr_csv should return a list of NormalizedTrade."""
        importer = CSVImporter()
        trades = importer._parse_ibkr_csv(ibkr_activity_csv, "test.csv")
        assert len(trades) >= 1
        for trade in trades:
            assert trade.broker == "ibkr"
            assert trade.symbol is not None

    def test_parse_ibkr_csv_skips_subtotals(self, ibkr_activity_csv):
        """Subtotal and Total rows should not be parsed as trades."""
        importer = CSVImporter()
        trades = importer._parse_ibkr_csv(ibkr_activity_csv, "test.csv")
        # Should only have data rows, not SubTotal/Total
        assert len(trades) == 5  # AAPL buy, AAPL sell, MSFT, option, future

    def test_parse_ibkr_csv_datetime_formats(self):
        """Various IBKR datetime formats should be parsed."""
        result1 = CSVImporter._parse_ibkr_csv_datetime("2025-01-15, 09:35:00")
        assert result1 is not None
        assert result1.year == 2025

        result2 = CSVImporter._parse_ibkr_csv_datetime("2025-01-15 09:35:00")
        assert result2 is not None

        result3 = CSVImporter._parse_ibkr_csv_datetime("")
        assert result3 is None

    def test_parse_ibkr_csv_no_trades(self, ibkr_activity_no_trades_csv):
        """IBKR CSV with no data rows should return empty list."""
        importer = CSVImporter()
        trades = importer._parse_ibkr_csv(ibkr_activity_no_trades_csv, "test.csv")
        assert len(trades) == 0

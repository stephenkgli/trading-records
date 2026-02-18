"""
Tests for the normalizer module and ingester normalization logic.

Tests field mapping from broker-specific formats to NormalizedTrade:
1. IBKR Flex Query XML field mapping (via IBKRFlexIngester._normalize_flex_trade)
2. IBKR Activity Statement CSV mapping (via CSVImporter._normalize_ibkr_csv_row)
3. Normalizer utility functions (normalize_side, normalize_asset_class, ensure_utc)
4. Timezone conversion

Reference: design-doc-final.md Sections 5.0, 5.3, 5.4, 5.5 field mapping tables.
"""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from lxml import etree

from backend.ingestion.normalizer import (
    ensure_utc,
    normalize_asset_class,
    normalize_side,
    safe_decimal,
    safe_str,
)
from backend.ingestion.ibkr_flex import IBKRFlexIngester
from backend.ingestion.csv_importer import CSVImporter

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ===========================================================================
# Normalizer Utility Functions
# ===========================================================================

class TestNormalizeSide:
    """Test the normalize_side utility function."""

    def test_buy_uppercase(self):
        assert normalize_side("BUY") == "buy"

    def test_sell_uppercase(self):
        assert normalize_side("SELL") == "sell"

    def test_buy_mixed_case(self):
        assert normalize_side("Buy") == "buy"

    def test_sell_mixed_case(self):
        assert normalize_side("Sell") == "sell"

    def test_bot_alias(self):
        assert normalize_side("BOT") == "buy"

    def test_sld_alias(self):
        assert normalize_side("SLD") == "sell"


class TestNormalizeAssetClass:
    """Test the normalize_asset_class utility function."""

    def test_stk_maps_to_stock(self):
        assert normalize_asset_class("STK") == "stock"

    def test_fut_maps_to_future(self):
        assert normalize_asset_class("FUT") == "future"

    def test_opt_maps_to_option(self):
        assert normalize_asset_class("OPT") == "option"

    def test_cash_maps_to_forex(self):
        assert normalize_asset_class("CASH") == "forex"

    def test_equity_maps_to_stock(self):
        assert normalize_asset_class("EQUITY") == "stock"

    def test_futures_maps_to_future(self):
        assert normalize_asset_class("FUTURES") == "future"


class TestEnsureUTC:
    """Test the ensure_utc utility function."""

    def test_naive_datetime_becomes_utc(self):
        """Naive datetime should be treated as UTC."""
        naive = datetime(2025, 1, 15, 14, 30, 0)
        result = ensure_utc(naive)
        assert result.tzinfo == timezone.utc
        assert result.hour == 14

    def test_utc_datetime_unchanged(self):
        """UTC datetime should pass through unchanged."""
        utc = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        result = ensure_utc(utc)
        assert result == utc


class TestSafeDecimal:
    """Test the safe_decimal utility function."""

    def test_string_to_decimal(self):
        assert safe_decimal("185.50") == Decimal("185.50")

    def test_none_returns_default(self):
        assert safe_decimal(None) == Decimal("0")

    def test_invalid_returns_default(self):
        assert safe_decimal("not_a_number") == Decimal("0")

    def test_int_to_decimal(self):
        assert safe_decimal(100) == Decimal("100")


class TestSafeStr:
    """Test the safe_str utility function."""

    def test_strips_whitespace(self):
        assert safe_str("  AAPL  ") == "AAPL"

    def test_none_returns_default(self):
        assert safe_str(None) == ""

    def test_none_returns_custom_default(self):
        assert safe_str(None, "N/A") == "N/A"


# ===========================================================================
# IBKR Flex Query XML Mapping (via IBKRFlexIngester)
# ===========================================================================

class TestIBKRFlexNormalization:
    """Test normalization of IBKR Flex Query XML trade elements."""

    @pytest.fixture
    def ingester(self):
        """Create an IBKRFlexIngester instance for testing normalization."""
        return IBKRFlexIngester(
            flex_token="test-token",
            query_id="999999",
            poll_interval=0,
            poll_max_attempts=1,
        )

    @pytest.fixture
    def sample_xml_trades(self, ibkr_flex_sample_xml):
        """Parse the sample XML and return trade elements using lxml."""
        root = etree.fromstring(ibkr_flex_sample_xml.encode())
        return root.xpath(".//Trade")

    def test_stock_buy_mapping(self, ingester, sample_xml_trades):
        """Verify correct field mapping for a stock BUY trade."""
        result = ingester._normalize_flex_trade(sample_xml_trades[0])

        assert result is not None
        assert result.broker == "ibkr"
        assert result.broker_exec_id == "EXEC001"
        assert result.account_id == "U1234567"
        assert result.symbol == "AAPL"
        assert result.asset_class == "stock"
        assert result.side == "buy"
        assert result.quantity == Decimal("100")
        assert result.price == Decimal("185.50")
        assert result.commission == Decimal("1.00")
        assert result.order_id == "ORD001"
        assert result.exchange == "SMART"
        assert result.currency == "USD"

    def test_stock_sell_mapping(self, ingester, sample_xml_trades):
        """Verify correct field mapping for a stock SELL trade."""
        result = ingester._normalize_flex_trade(sample_xml_trades[1])

        assert result is not None
        assert result.side == "sell"
        assert result.symbol == "AAPL"
        assert result.quantity == Decimal("100")
        assert result.price == Decimal("190.25")

    def test_option_mapping(self, ingester, sample_xml_trades):
        """Verify option trades map assetCategory OPT to asset_class option."""
        result = ingester._normalize_flex_trade(sample_xml_trades[2])

        assert result is not None
        assert result.asset_class == "option"
        assert result.underlying == "AAPL"
        assert result.symbol == "AAPL 250221C00190000"
        assert result.quantity == Decimal("5")
        assert result.price == Decimal("3.50")

    def test_future_mapping(self, ingester, sample_xml_trades):
        """Verify future trades map assetCategory FUT to asset_class future."""
        result = ingester._normalize_flex_trade(sample_xml_trades[3])

        assert result is not None
        assert result.asset_class == "future"
        assert result.underlying == "ES"
        assert result.symbol == "ESH5"
        assert result.exchange == "CME"

    def test_forex_mapping(self, ingester, sample_xml_trades):
        """Verify forex trades map assetCategory CASH to asset_class forex."""
        result = ingester._normalize_flex_trade(sample_xml_trades[4])

        assert result is not None
        assert result.asset_class == "forex"
        assert result.symbol == "EUR.USD"

    def test_raw_data_preserved(self, ingester, sample_xml_trades):
        """Verify that raw broker data is preserved in raw_data field."""
        result = ingester._normalize_flex_trade(sample_xml_trades[0])

        assert result is not None
        assert isinstance(result.raw_data, dict)
        assert "tradeID" in result.raw_data

    def test_commission_stored_as_positive(self, ingester, sample_xml_trades):
        """IBKR reports commission as negative; normalizer should store as positive."""
        result = ingester._normalize_flex_trade(sample_xml_trades[0])

        assert result is not None
        assert result.commission >= 0

    def test_all_trades_parsed(self, ingester, sample_xml_trades):
        """All 5 trades in sample XML should be parseable."""
        results = [ingester._normalize_flex_trade(t) for t in sample_xml_trades]
        valid_results = [r for r in results if r is not None]
        assert len(valid_results) == 5
        for r in valid_results:
            assert r.broker == "ibkr"
            assert r.broker_exec_id is not None


# ===========================================================================
# IBKR Flex Query Timezone Conversion
# ===========================================================================

class TestIBKRTimezoneConversion:
    """Test that IBKR Flex dateTime fields are converted to UTC."""

    @pytest.fixture
    def ingester(self):
        return IBKRFlexIngester(
            flex_token="test", query_id="999", poll_interval=0, poll_max_attempts=1
        )

    @pytest.fixture
    def sample_xml_trades(self, ibkr_flex_sample_xml):
        root = etree.fromstring(ibkr_flex_sample_xml.encode())
        return root.xpath(".//Trade")

    def test_datetime_is_utc(self, ingester, sample_xml_trades):
        """Normalized executed_at should have UTC timezone info."""
        result = ingester._normalize_flex_trade(sample_xml_trades[0])

        assert result is not None
        assert result.executed_at.tzinfo is not None
        assert result.executed_at.utcoffset().total_seconds() == 0

    def test_datetime_parsed_correctly(self, ingester, sample_xml_trades):
        """The dateTime '2025-01-15;09:35:00' should be parsed to a valid datetime."""
        result = ingester._normalize_flex_trade(sample_xml_trades[0])

        assert result is not None
        assert result.executed_at.year == 2025
        assert result.executed_at.month == 1


# ===========================================================================
# IBKR Activity Statement CSV Mapping (via CSVImporter)
# ===========================================================================

class TestIBKRCSVNormalization:
    """Test normalization of IBKR Activity Statement CSV rows."""

    @pytest.fixture
    def importer(self):
        return CSVImporter()

    def test_ibkr_csv_parses_trades(self, importer, ibkr_activity_csv):
        """IBKR CSV should parse trade data rows."""
        trades = importer._parse_ibkr_csv(ibkr_activity_csv, "ibkr_activity.csv")
        assert len(trades) >= 1

    def test_ibkr_csv_stock_fields(self, importer, ibkr_activity_csv):
        """First parsed trade should have correct stock fields."""
        trades = importer._parse_ibkr_csv(ibkr_activity_csv, "ibkr_activity.csv")

        # Find a stock trade
        stock_trades = [t for t in trades if t.asset_class == "stock"]
        assert len(stock_trades) >= 1

        trade = stock_trades[0]
        assert trade.broker == "ibkr"
        assert trade.symbol == "AAPL"
        assert trade.currency == "USD"

    def test_ibkr_csv_broker_exec_id_generated(self, importer, ibkr_activity_csv):
        """CSV trades should have a broker_exec_id (either from CSV or hash)."""
        trades = importer._parse_ibkr_csv(ibkr_activity_csv, "ibkr_activity.csv")
        for trade in trades:
            assert trade.broker_exec_id is not None
            assert len(trade.broker_exec_id) > 0

    def test_ibkr_csv_raw_data_preserved(self, importer, ibkr_activity_csv):
        """Raw CSV row data should be preserved."""
        trades = importer._parse_ibkr_csv(ibkr_activity_csv, "ibkr_activity.csv")
        for trade in trades:
            assert isinstance(trade.raw_data, dict)

    def test_ibkr_csv_no_trades_file(self, importer, ibkr_activity_no_trades_csv):
        """IBKR CSV with no trade data rows should produce empty list."""
        trades = importer._parse_ibkr_csv(ibkr_activity_no_trades_csv, "no_trades.csv")
        assert len(trades) == 0

"""Tests for normalizer utilities and CSV normalization logic."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.ingestion.csv_importer import CSVImporter
from backend.ingestion.normalizer import (
    ensure_utc,
    normalize_asset_class,
    normalize_side,
    safe_decimal,
    safe_str,
)


class TestNormalizeSide:
    """Test side normalization."""

    def test_buy_variants(self):
        assert normalize_side("BUY") == "buy"
        assert normalize_side("Buy") == "buy"
        assert normalize_side("BOT") == "buy"

    def test_sell_variants(self):
        assert normalize_side("SELL") == "sell"
        assert normalize_side("Sell") == "sell"
        assert normalize_side("SLD") == "sell"


class TestNormalizeAssetClass:
    """Test asset class normalization."""

    def test_class_aliases(self):
        assert normalize_asset_class("STK") == "stock"
        assert normalize_asset_class("FUT") == "future"
        assert normalize_asset_class("OPT") == "option"
        assert normalize_asset_class("CASH") == "forex"
        assert normalize_asset_class("EQUITY") == "stock"
        assert normalize_asset_class("FUTURES") == "future"


class TestEnsureUTC:
    """Test UTC conversion helper."""

    def test_naive_datetime_becomes_utc(self):
        result = ensure_utc(datetime(2025, 1, 15, 14, 30, 0))
        assert result.tzinfo == timezone.utc
        assert result.hour == 14

    def test_utc_datetime_unchanged(self):
        utc_dt = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        assert ensure_utc(utc_dt) == utc_dt


class TestSafeDecimal:
    """Test decimal parsing helper."""

    def test_valid_values(self):
        assert safe_decimal("185.50") == Decimal("185.50")
        assert safe_decimal(100) == Decimal("100")

    def test_invalid_values(self):
        assert safe_decimal(None) == Decimal("0")
        assert safe_decimal("not_a_number") == Decimal("0")


class TestSafeStr:
    """Test string normalization helper."""

    def test_safe_str(self):
        assert safe_str("  AAPL  ") == "AAPL"
        assert safe_str(None) == ""
        assert safe_str(None, "N/A") == "N/A"


class TestIBKRCSVNormalization:
    """Test normalization from IBKR activity CSV rows."""

    @pytest.fixture
    def importer(self) -> CSVImporter:
        return CSVImporter()

    def test_ibkr_csv_parses_trades(self, importer: CSVImporter, ibkr_activity_csv: str):
        trades = importer._parse_ibkr_csv(ibkr_activity_csv, "ibkr_activity.csv")
        assert len(trades) >= 1

    def test_ibkr_csv_stock_fields(
        self, importer: CSVImporter, ibkr_activity_csv: str
    ):
        trades = importer._parse_ibkr_csv(ibkr_activity_csv, "ibkr_activity.csv")
        stock_trades = [t for t in trades if t.asset_class == "stock"]
        assert stock_trades

        trade = stock_trades[0]
        assert trade.broker == "ibkr"
        assert trade.symbol
        assert trade.currency == "USD"

    def test_ibkr_csv_broker_exec_id_generated(
        self, importer: CSVImporter, ibkr_activity_csv: str
    ):
        trades = importer._parse_ibkr_csv(ibkr_activity_csv, "ibkr_activity.csv")
        for trade in trades:
            assert trade.broker_exec_id

    def test_ibkr_csv_raw_data_preserved(
        self, importer: CSVImporter, ibkr_activity_csv: str
    ):
        trades = importer._parse_ibkr_csv(ibkr_activity_csv, "ibkr_activity.csv")
        for trade in trades:
            assert isinstance(trade.raw_data, dict)

    def test_ibkr_csv_no_trades_file(
        self, importer: CSVImporter, ibkr_activity_no_trades_csv: str
    ):
        trades = importer._parse_ibkr_csv(ibkr_activity_no_trades_csv, "no_trades.csv")
        assert len(trades) == 0

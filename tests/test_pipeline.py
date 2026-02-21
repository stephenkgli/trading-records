"""
Tests for the IngestionPipeline and import source interfaces.

Verifies:
1. IngestionPipeline.run() delegates to BaseIngester.import_records()
2. _PipelineIngester sets source dynamically
3. ImportSource ABC enforcement
4. SourceRegistry register/get/available
5. CSVSource fetch_normalized_trades
6. Pipeline end-to-end with CSVSource
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from backend.ingestion.pipeline import IngestionPipeline, _PipelineIngester
from backend.ingestion.sources.base import ImportSource, SourceRegistry
from backend.ingestion.sources.csv_source import CSVSource
from backend.schemas.trade import NormalizedTrade


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeSource(ImportSource):
    """Test import source that returns fixed trades."""

    source_name = "fake"

    def __init__(self, trades: list[NormalizedTrade] | None = None) -> None:
        self._trades = trades or []

    def fetch_normalized_trades(
        self, *, db=None, **kwargs
    ) -> list[NormalizedTrade]:
        return self._trades


def _make_trade(**overrides) -> NormalizedTrade:
    """Create a NormalizedTrade with sensible defaults."""
    defaults = {
        "broker": "ibkr",
        "broker_exec_id": f"PIPE{id(overrides):08x}",
        "account_id": "U1234567",
        "symbol": "AAPL",
        "asset_class": "stock",
        "side": "buy",
        "quantity": Decimal("100"),
        "price": Decimal("185.50"),
        "commission": Decimal("1.00"),
        "executed_at": datetime(2025, 1, 15, 14, 35, 0, tzinfo=timezone.utc),
        "currency": "USD",
        "raw_data": {"test": True},
    }
    defaults.update(overrides)
    return NormalizedTrade(**defaults)


# ===========================================================================
# _PipelineIngester
# ===========================================================================

class TestPipelineIngester:
    """Test the internal _PipelineIngester subclass."""

    def test_source_set_dynamically(self):
        """_PipelineIngester should use the source_name passed to constructor."""
        ingester = _PipelineIngester(source_name="my_source")
        assert ingester.source == "my_source"

    def test_source_different_values(self):
        """Different source names should work."""
        a = _PipelineIngester(source_name="csv")
        b = _PipelineIngester(source_name="manual_import")
        assert a.source == "csv"
        assert b.source == "manual_import"


# ===========================================================================
# ImportSource ABC
# ===========================================================================

class TestImportSourceABC:
    """Test that ImportSource enforces the abstract interface."""

    def test_cannot_instantiate_abstract(self):
        """ImportSource cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ImportSource()

    def test_concrete_subclass_works(self):
        """A concrete subclass with fetch_normalized_trades should work."""
        source = _FakeSource()
        assert source.source_name == "fake"
        assert source.fetch_normalized_trades() == []


# ===========================================================================
# SourceRegistry
# ===========================================================================

class TestSourceRegistry:
    """Test the SourceRegistry register/get/available."""

    def test_register_and_get(self):
        """Registered source should be retrievable by name."""
        # CSVSource is already registered via @SourceRegistry.register
        cls = SourceRegistry.get("csv")
        assert cls is CSVSource

    def test_get_unknown_returns_none(self):
        """Unknown source name should return None."""
        assert SourceRegistry.get("nonexistent_source_xyz") is None

    def test_available_includes_csv(self):
        """Available sources should include 'csv'."""
        available = SourceRegistry.available()
        assert "csv" in available


# ===========================================================================
# CSVSource
# ===========================================================================

class TestCSVSource:
    """Test the CSVSource import source."""

    def test_source_name(self):
        """CSVSource.source_name should be 'csv'."""
        source = CSVSource()
        assert source.source_name == "csv"

    def test_fetch_ibkr_csv(self, ibkr_activity_csv):
        """CSVSource should parse IBKR CSV and return normalized trades."""
        source = CSVSource()
        trades = source.fetch_normalized_trades(
            file_content=ibkr_activity_csv, filename="ibkr_activity.csv"
        )
        assert len(trades) > 0
        for t in trades:
            assert t.broker == "ibkr"

    def test_fetch_tradovate_perf_csv(
        self, tradovate_performance_csv, tradovate_expected_trade_count
    ):
        """CSVSource should parse Tradovate Performance CSV."""
        source = CSVSource()
        trades = source.fetch_normalized_trades(
            file_content=tradovate_performance_csv, filename="Performance.csv"
        )
        assert len(trades) == tradovate_expected_trade_count
        for t in trades:
            assert t.broker == "tradovate"

    def test_fetch_bytes_input(self, ibkr_activity_csv):
        """CSVSource should handle bytes input."""
        source = CSVSource()
        trades = source.fetch_normalized_trades(
            file_content=ibkr_activity_csv.encode("utf-8"),
            filename="ibkr.csv",
        )
        assert len(trades) > 0

    def test_unknown_format_raises(self):
        """CSVSource should raise ValueError for unknown format."""
        source = CSVSource()
        with pytest.raises(ValueError, match="Unknown CSV format"):
            source.fetch_normalized_trades(
                file_content="col1,col2\nval1,val2\n",
                filename="unknown.csv",
            )


# ===========================================================================
# IngestionPipeline
# ===========================================================================

class TestIngestionPipeline:
    """Test the IngestionPipeline orchestrator."""

    def test_run_with_empty_source(self, db_session):
        """Pipeline with a source that returns no trades should succeed."""
        pipeline = IngestionPipeline()
        source = _FakeSource(trades=[])
        result = pipeline.run(source, db=db_session)

        assert result.records_total == 0
        assert result.records_imported == 0
        assert result.status == "success"

    def test_run_with_trades(self, db_session):
        """Pipeline with valid trades should import them."""
        trades = [
            _make_trade(broker_exec_id="PIPE001"),
            _make_trade(broker_exec_id="PIPE002"),
        ]
        pipeline = IngestionPipeline()
        source = _FakeSource(trades=trades)
        result = pipeline.run(source, db=db_session)

        assert result.records_total == 2
        assert result.records_imported == 2
        assert result.source == "fake"

    def test_run_dedup(self, db_session):
        """Pipeline should deduplicate on second run."""
        trades = [_make_trade(broker_exec_id="PIPEDUP01")]
        pipeline = IngestionPipeline()
        source = _FakeSource(trades=trades)

        result1 = pipeline.run(source, db=db_session)
        assert result1.records_imported == 1

        result2 = pipeline.run(source, db=db_session)
        assert result2.records_imported == 0
        assert result2.records_skipped_dup == 1

    def test_run_source_name_propagated(self, db_session):
        """Pipeline result.source should match the ImportSource.source_name."""
        source = _FakeSource(trades=[])
        pipeline = IngestionPipeline()
        result = pipeline.run(source, db=db_session)
        assert result.source == "fake"

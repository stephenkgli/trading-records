"""
Tests for the data validation layer.

Tests the 6 validation rules defined in the design document (Section 5.1):
1. Required fields: symbol, price, quantity, executed_at, side, broker_exec_id must be non-null
2. Price range: price > 0
3. Quantity range: quantity != 0
4. Timestamp sanity: executed_at not in the future and not before 2000-01-01
5. Broker enum: broker must be one of "ibkr", "tradovate"
6. Asset class enum: asset_class must be one of "stock", "future", "option", "forex"

Each rule has positive (valid) and negative (invalid) test cases.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.ingestion.validator import validate_trade, validate_batch, ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_trade_dict() -> dict:
    """Return a dictionary of valid trade fields for constructing NormalizedTrade."""
    return {
        "broker": "ibkr",
        "broker_exec_id": "EXEC001",
        "account_id": "U1234567",
        "symbol": "AAPL",
        "underlying": None,
        "asset_class": "stock",
        "side": "buy",
        "quantity": Decimal("100"),
        "price": Decimal("185.50"),
        "commission": Decimal("1.00"),
        "executed_at": datetime(2025, 1, 15, 14, 35, 0, tzinfo=timezone.utc),
        "order_id": "ORD001",
        "exchange": "SMART",
        "currency": "USD",
        "raw_data": {"test": True},
    }


# ===========================================================================
# Rule 1: Required fields
# ===========================================================================

class TestRequiredFields:
    """Validate that required fields must be non-null."""

    REQUIRED_STRING_FIELDS = ["symbol", "side", "broker_exec_id"]

    def test_valid_trade_passes_required_fields(self, make_normalized_trade):
        """A trade with all required fields set should pass validation."""
        trade = make_normalized_trade()
        errors = validate_trade(trade)
        assert errors == []

    @pytest.mark.parametrize("field", REQUIRED_STRING_FIELDS)
    def test_empty_string_required_field_fails(self, field):
        """Required string fields set to empty string should fail validation."""
        from backend.schemas.trade import NormalizedTrade

        data = _valid_trade_dict()
        data[field] = ""
        trade = NormalizedTrade(**data)
        errors = validate_trade(trade)
        assert len(errors) > 0, f"Expected validation error for empty {field}"
        assert any(field in e.field for e in errors)


# ===========================================================================
# Rule 2: Price range (price > 0)
# ===========================================================================

class TestPriceRange:
    """Validate that price must be greater than zero."""

    def test_positive_price_passes(self, make_normalized_trade):
        """A trade with a positive price should pass validation."""
        trade = make_normalized_trade(price=Decimal("185.50"))
        errors = validate_trade(trade)
        price_errors = [e for e in errors if "price" in e.field.lower()]
        assert price_errors == []

    def test_zero_price_fails(self, make_normalized_trade):
        """A trade with price = 0 should fail validation."""
        trade = make_normalized_trade(price=Decimal("0"))
        errors = validate_trade(trade)
        price_errors = [e for e in errors if "price" in e.field.lower()]
        assert len(price_errors) > 0

    def test_negative_price_fails(self, make_normalized_trade):
        """A trade with negative price should fail validation."""
        trade = make_normalized_trade(price=Decimal("-10.00"))
        errors = validate_trade(trade)
        price_errors = [e for e in errors if "price" in e.field.lower()]
        assert len(price_errors) > 0

    def test_very_small_positive_price_passes(self, make_normalized_trade):
        """A very small but positive price (e.g., penny stock) should pass."""
        trade = make_normalized_trade(price=Decimal("0.01"))
        errors = validate_trade(trade)
        price_errors = [e for e in errors if "price" in e.field.lower()]
        assert price_errors == []


# ===========================================================================
# Rule 3: Quantity range (quantity != 0)
# ===========================================================================

class TestQuantityRange:
    """Validate that quantity must not be zero."""

    def test_positive_quantity_passes(self, make_normalized_trade):
        """A trade with positive quantity should pass validation."""
        trade = make_normalized_trade(quantity=Decimal("100"))
        errors = validate_trade(trade)
        qty_errors = [e for e in errors if "quantity" in e.field.lower()]
        assert qty_errors == []

    def test_negative_quantity_passes(self, make_normalized_trade):
        """A trade with negative quantity (short sells) should pass validation."""
        trade = make_normalized_trade(quantity=Decimal("-50"))
        errors = validate_trade(trade)
        qty_errors = [e for e in errors if "quantity" in e.field.lower()]
        assert qty_errors == []

    def test_zero_quantity_fails(self, make_normalized_trade):
        """A trade with quantity = 0 should fail validation."""
        trade = make_normalized_trade(quantity=Decimal("0"))
        errors = validate_trade(trade)
        qty_errors = [e for e in errors if "quantity" in e.field.lower()]
        assert len(qty_errors) > 0

    def test_fractional_quantity_passes(self, make_normalized_trade):
        """Fractional shares (e.g., 0.5) should be valid."""
        trade = make_normalized_trade(quantity=Decimal("0.5"))
        errors = validate_trade(trade)
        qty_errors = [e for e in errors if "quantity" in e.field.lower()]
        assert qty_errors == []


# ===========================================================================
# Rule 4: Timestamp sanity
# ===========================================================================

class TestTimestampSanity:
    """Validate timestamp is not in the future and not before 2000-01-01."""

    def test_reasonable_timestamp_passes(self, make_normalized_trade):
        """A timestamp within a reasonable range should pass."""
        trade = make_normalized_trade(
            executed_at=datetime(2025, 1, 15, 14, 35, 0, tzinfo=timezone.utc)
        )
        errors = validate_trade(trade)
        ts_errors = [e for e in errors if "executed_at" in e.field.lower()]
        assert ts_errors == []

    def test_future_timestamp_fails(self, make_normalized_trade):
        """A timestamp in the future should fail validation."""
        future = datetime.now(timezone.utc) + timedelta(days=30)
        trade = make_normalized_trade(executed_at=future)
        errors = validate_trade(trade)
        ts_errors = [e for e in errors if "executed_at" in e.field.lower()]
        assert len(ts_errors) > 0

    def test_very_old_timestamp_fails(self, make_normalized_trade):
        """A timestamp before 2000-01-01 should fail validation."""
        old = datetime(1999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        trade = make_normalized_trade(executed_at=old)
        errors = validate_trade(trade)
        ts_errors = [e for e in errors if "executed_at" in e.field.lower()]
        assert len(ts_errors) > 0

    def test_y2k_boundary_passes(self, make_normalized_trade):
        """A timestamp exactly at 2000-01-01T00:00:00Z should pass."""
        y2k = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        trade = make_normalized_trade(executed_at=y2k)
        errors = validate_trade(trade)
        ts_errors = [e for e in errors if "executed_at" in e.field.lower()]
        assert ts_errors == []

    def test_now_timestamp_passes(self, make_normalized_trade):
        """A timestamp at the current moment should pass (not future)."""
        now = datetime.now(timezone.utc)
        trade = make_normalized_trade(executed_at=now)
        errors = validate_trade(trade)
        ts_errors = [e for e in errors if "executed_at" in e.field.lower()]
        assert ts_errors == []


# ===========================================================================
# Rule 5: Broker enum
# ===========================================================================

class TestBrokerEnum:
    """Validate that broker must be one of the allowed values."""

    @pytest.mark.parametrize("broker", ["ibkr", "tradovate"])
    def test_valid_broker_passes(self, make_normalized_trade, broker):
        """Valid broker values should pass validation."""
        trade = make_normalized_trade(broker=broker)
        errors = validate_trade(trade)
        broker_errors = [e for e in errors if "broker" in e.field.lower()]
        assert broker_errors == []

    def test_invalid_broker_fails(self):
        """An invalid broker value should fail at Pydantic Literal validation."""
        from backend.schemas.trade import NormalizedTrade

        data = _valid_trade_dict()
        data["broker"] = "robinhood"
        try:
            trade = NormalizedTrade(**data)
            errors = validate_trade(trade)
            assert len(errors) > 0
        except (ValueError, TypeError):
            # Pydantic Literal type rejects it — acceptable behavior
            pass

    def test_uppercase_broker_fails(self):
        """Broker value with wrong case should fail (strict Literal)."""
        from backend.schemas.trade import NormalizedTrade

        data = _valid_trade_dict()
        data["broker"] = "IBKR"
        try:
            trade = NormalizedTrade(**data)
            errors = validate_trade(trade)
            assert len(errors) > 0
        except (ValueError, TypeError):
            pass


# ===========================================================================
# Rule 6: Asset class enum
# ===========================================================================

class TestAssetClassEnum:
    """Validate that asset_class must be one of the allowed values."""

    @pytest.mark.parametrize("asset_class", ["stock", "future", "option", "forex"])
    def test_valid_asset_class_passes(self, make_normalized_trade, asset_class):
        """Valid asset_class values should pass validation."""
        trade = make_normalized_trade(asset_class=asset_class)
        errors = validate_trade(trade)
        ac_errors = [e for e in errors if "asset_class" in e.field.lower()]
        assert ac_errors == []

    def test_invalid_asset_class_fails(self):
        """An invalid asset_class should fail at Pydantic Literal."""
        from backend.schemas.trade import NormalizedTrade

        data = _valid_trade_dict()
        data["asset_class"] = "crypto"
        try:
            trade = NormalizedTrade(**data)
            errors = validate_trade(trade)
            assert len(errors) > 0
        except (ValueError, TypeError):
            pass

    def test_uppercase_asset_class_fails(self):
        """Asset class with wrong case should fail (strict Literal)."""
        from backend.schemas.trade import NormalizedTrade

        data = _valid_trade_dict()
        data["asset_class"] = "Stock"
        try:
            trade = NormalizedTrade(**data)
            errors = validate_trade(trade)
            assert len(errors) > 0
        except (ValueError, TypeError):
            pass


# ===========================================================================
# Batch validation (validate_batch)
# ===========================================================================

class TestBatchValidation:
    """Test validate_batch which processes a list of trades."""

    def test_all_valid_trades(self, make_normalized_trade):
        """A batch of valid trades should all pass."""
        trades = [make_normalized_trade(symbol=f"SYM{i}") for i in range(5)]
        result = validate_batch(trades)
        assert len(result.valid) == 5
        assert len(result.errors) == 0

    def test_mixed_valid_invalid(self, make_normalized_trade):
        """A batch with some invalid trades should separate them correctly."""
        trades = [
            make_normalized_trade(symbol="AAPL", price=Decimal("100")),
            make_normalized_trade(symbol="BAD", price=Decimal("0")),
            make_normalized_trade(symbol="MSFT", price=Decimal("200")),
        ]
        result = validate_batch(trades)
        assert len(result.valid) == 2
        assert len(result.errors) == 1

    def test_empty_batch(self):
        """An empty batch should return empty results."""
        result = validate_batch([])
        assert len(result.valid) == 0
        assert len(result.errors) == 0

    def test_all_invalid_trades(self, make_normalized_trade):
        """A batch where all trades are invalid."""
        trades = [
            make_normalized_trade(price=Decimal("0")),
            make_normalized_trade(price=Decimal("-1")),
            make_normalized_trade(quantity=Decimal("0")),
        ]
        result = validate_batch(trades)
        assert len(result.valid) == 0
        assert len(result.errors) == 3

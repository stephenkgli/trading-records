"""Normalization helpers for broker-specific data to NormalizedTrade."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


def safe_decimal(value: str | float | int | Decimal | None, default: Decimal = Decimal("0")) -> Decimal:
    """Safely convert a value to Decimal."""
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


def safe_str(value: str | None, default: str = "") -> str:
    """Safely convert a value to stripped string."""
    if value is None:
        return default
    return str(value).strip()


def normalize_side(raw_side: str) -> str:
    """Normalize trade side to 'buy' or 'sell'."""
    side = raw_side.strip().upper()
    if side in ("BUY", "B", "BOT", "BOUGHT"):
        return "buy"
    if side in ("SELL", "S", "SLD", "SOLD"):
        return "sell"
    return raw_side.lower()


def normalize_asset_class(raw: str) -> str:
    """Normalize asset class to standard enum values."""
    mapping = {
        "STK": "stock",
        "STOCK": "stock",
        "STOCKS": "stock",
        "EQUITY": "stock",
        "EQ": "stock",
        "FUT": "future",
        "FUTURE": "future",
        "FUTURES": "future",
        "OPT": "option",
        "OPTION": "option",
        "OPTIONS": "option",
        "EQUITY AND INDEX OPTIONS": "option",
        "CASH": "forex",
        "FOREX": "forex",
        "FX": "forex",
    }
    return mapping.get(raw.strip().upper(), raw.lower())


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware UTC.

    If naive, assume UTC. If has another timezone, convert to UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

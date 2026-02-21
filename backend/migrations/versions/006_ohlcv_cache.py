"""Add OHLCV cache table.

Revision ID: 006
Revises: 005
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ohlcv_cache",
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("interval", sa.String(10), nullable=False),
        sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(18, 8), nullable=False),
        sa.Column("high", sa.Numeric(18, 8), nullable=False),
        sa.Column("low", sa.Numeric(18, 8), nullable=False),
        sa.Column("close", sa.Numeric(18, 8), nullable=False),
        sa.Column("volume", sa.BigInteger, nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("asset_class", sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "interval", "bar_time"),
    )
    op.create_index(
        "idx_ohlcv_cache_symbol_interval",
        "ohlcv_cache",
        ["symbol", "interval", "bar_time"],
    )


def downgrade() -> None:
    op.drop_index("idx_ohlcv_cache_symbol_interval")
    op.drop_table("ohlcv_cache")

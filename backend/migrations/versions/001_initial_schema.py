"""Initial schema with all tables and indexes.

Revision ID: 001
Revises:
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # import_logs table
    op.create_table(
        "import_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("records_total", sa.Integer, server_default="0"),
        sa.Column("records_imported", sa.Integer, server_default="0"),
        sa.Column("records_skipped_dup", sa.Integer, server_default="0"),
        sa.Column("records_failed", sa.Integer, server_default="0"),
        sa.Column("errors", postgresql.JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # trades table
    op.create_table(
        "trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker", sa.String(20), nullable=False),
        sa.Column("broker_exec_id", sa.String(255), nullable=False),
        sa.Column(
            "import_log_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_logs.id"),
            nullable=True,
        ),
        sa.Column("account_id", sa.String(50), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("underlying", sa.String(50), nullable=True),
        sa.Column("asset_class", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("price", sa.Numeric(18, 8), nullable=False),
        sa.Column("commission", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("order_id", sa.String(100), nullable=True),
        sa.Column("exchange", sa.String(50), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("raw_data", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # trades indexes
    op.create_index("idx_trades_executed_at", "trades", ["executed_at"])
    op.create_index("idx_trades_symbol_executed_at", "trades", ["symbol", "executed_at"])
    op.create_index("idx_trades_broker_account", "trades", ["broker", "account_id"])
    op.create_index(
        "idx_trades_broker_exec_id", "trades", ["broker", "broker_exec_id"], unique=True
    )
    op.create_index("idx_trades_import_log_id", "trades", ["import_log_id"])

    # trade_groups table
    op.create_table(
        "trade_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", sa.String(50), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("asset_class", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("strategy_tag", sa.String(100), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column("realized_pnl", sa.Numeric(18, 8), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )

    # trade_groups indexes
    op.create_index("idx_trade_groups_status", "trade_groups", ["status"])
    op.create_index(
        "idx_trade_groups_account_symbol", "trade_groups", ["account_id", "symbol"]
    )

    # trade_group_legs table
    op.create_table(
        "trade_group_legs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "trade_group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trade_groups.id"),
            nullable=False,
        ),
        sa.Column(
            "trade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trades.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(10), nullable=False),
    )

    op.create_index(
        "idx_trade_group_legs_group_id", "trade_group_legs", ["trade_group_id"]
    )


def downgrade() -> None:
    op.drop_table("trade_group_legs")
    op.drop_table("trade_groups")
    op.drop_table("trades")
    op.drop_table("import_logs")

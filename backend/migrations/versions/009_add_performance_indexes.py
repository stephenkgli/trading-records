"""Add performance-oriented composite indexes.

Revision ID: 009
Revises: 008
Create Date: 2026-03-05
"""

from __future__ import annotations

from alembic import op

# revision identifiers
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                idx_trades_account_symbol_executed_at
                ON trades (account_id, symbol, executed_at)
                """
            )
            op.execute(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                idx_trade_groups_account_symbol_status
                ON trade_groups (account_id, symbol, status)
                """
            )
        return

    op.create_index(
        "idx_trades_account_symbol_executed_at",
        "trades",
        ["account_id", "symbol", "executed_at"],
    )
    op.create_index(
        "idx_trade_groups_account_symbol_status",
        "trade_groups",
        ["account_id", "symbol", "status"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "DROP INDEX CONCURRENTLY IF EXISTS idx_trade_groups_account_symbol_status"
            )
            op.execute(
                "DROP INDEX CONCURRENTLY IF EXISTS idx_trades_account_symbol_executed_at"
            )
        return

    op.drop_index("idx_trade_groups_account_symbol_status", table_name="trade_groups")
    op.drop_index("idx_trades_account_symbol_executed_at", table_name="trades")

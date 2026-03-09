"""Add index on trade_group_legs (trade_id).

Supports the by-activity-date query that joins trades -> trade_group_legs.

Revision ID: 013
Revises: 012
Create Date: 2026-03-09
"""

from __future__ import annotations

from alembic import op

# revision identifiers
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                idx_trade_group_legs_trade_id
                ON trade_group_legs (trade_id)
                """
            )
        return

    op.create_index(
        "idx_trade_group_legs_trade_id",
        "trade_group_legs",
        ["trade_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "DROP INDEX CONCURRENTLY IF EXISTS idx_trade_group_legs_trade_id"
            )
        return

    op.drop_index("idx_trade_group_legs_trade_id", table_name="trade_group_legs")

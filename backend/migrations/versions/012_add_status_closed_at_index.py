"""Add composite index on trade_groups (status, closed_at).

Supports the new closed_from/closed_to filter on the groups API,
which always queries with status='closed' and a closed_at range.

Revision ID: 012
Revises: 011
Create Date: 2026-03-09
"""

from __future__ import annotations

from alembic import op

# revision identifiers
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                idx_trade_groups_status_closed_at
                ON trade_groups (status, closed_at)
                """
            )
        return

    op.create_index(
        "idx_trade_groups_status_closed_at",
        "trade_groups",
        ["status", "closed_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "DROP INDEX CONCURRENTLY IF EXISTS idx_trade_groups_status_closed_at"
            )
        return

    op.drop_index("idx_trade_groups_status_closed_at", table_name="trade_groups")

"""Add PostgreSQL GIN index for trades.raw_data.

Revision ID: 011
Revises: 010
Create Date: 2026-03-05
"""

from __future__ import annotations

from alembic import op

# revision identifiers
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_raw_data_gin
            ON trades USING GIN (raw_data)
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_trades_raw_data_gin")

"""Add daily_summaries materialized view.

Revision ID: 002
Revises: 001
Create Date: 2026-02-18
"""

from alembic import op

# revision identifiers
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW daily_summaries AS
        SELECT
            date_trunc('day', t.executed_at AT TIME ZONE 'UTC')::date AS date,
            t.account_id,
            SUM(CASE
                WHEN t.side = 'sell' THEN t.price * t.quantity
                WHEN t.side = 'buy' THEN -t.price * t.quantity
            END) AS gross_pnl,
            SUM(CASE
                WHEN t.side = 'sell' THEN t.price * t.quantity
                WHEN t.side = 'buy' THEN -t.price * t.quantity
            END) - SUM(ABS(t.commission)) AS net_pnl,
            SUM(ABS(t.commission)) AS commissions,
            COUNT(*) AS trade_count,
            COUNT(*) FILTER (WHERE t.side = 'sell' AND t.price * t.quantity > 0) AS win_count,
            COUNT(*) FILTER (WHERE t.side = 'sell' AND t.price * t.quantity <= 0) AS loss_count
        FROM trades t
        GROUP BY 1, 2;
    """)

    op.execute(
        "CREATE UNIQUE INDEX ON daily_summaries (date, account_id);"
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_summaries;")

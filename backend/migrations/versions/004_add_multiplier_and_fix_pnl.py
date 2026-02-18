"""Add multiplier column to trades and fix daily_summaries P&L calculation.

The trades table lacked a contract multiplier, causing futures P&L to be
computed as raw price differences instead of dollar amounts.

This migration:
1. Adds `multiplier` column to `trades` (default 1).
2. Rebuilds `daily_summaries` materialized view to include `t.multiplier`
   in gross_pnl / net_pnl calculations.

Revision ID: 004
Revises: 003
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add multiplier column to trades
    op.add_column(
        "trades",
        sa.Column(
            "multiplier",
            sa.Numeric(18, 8),
            nullable=False,
            server_default="1",
            comment="Contract multiplier (value per point for futures, 1 for stocks)",
        ),
    )

    # 2. Rebuild daily_summaries materialized view with multiplier
    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_summaries;")

    op.execute("""
        CREATE MATERIALIZED VIEW daily_summaries AS
        SELECT
            COALESCE(t_agg.date, g_agg.date) AS date,
            COALESCE(t_agg.account_id, g_agg.account_id) AS account_id,
            COALESCE(t_agg.gross_pnl, 0) AS gross_pnl,
            COALESCE(t_agg.net_pnl, 0) AS net_pnl,
            COALESCE(t_agg.commissions, 0) AS commissions,
            COALESCE(t_agg.trade_count, 0) AS trade_count,
            COALESCE(g_agg.win_count, 0) AS win_count,
            COALESCE(g_agg.loss_count, 0) AS loss_count
        FROM (
            SELECT
                date_trunc('day', t.executed_at AT TIME ZONE 'UTC')::date AS date,
                t.account_id,
                SUM(CASE
                    WHEN t.side = 'sell' THEN t.price * t.quantity * t.multiplier
                    WHEN t.side = 'buy' THEN -t.price * t.quantity * t.multiplier
                END) AS gross_pnl,
                SUM(CASE
                    WHEN t.side = 'sell' THEN t.price * t.quantity * t.multiplier
                    WHEN t.side = 'buy' THEN -t.price * t.quantity * t.multiplier
                END) - SUM(ABS(t.commission)) AS net_pnl,
                SUM(ABS(t.commission)) AS commissions,
                COUNT(*) AS trade_count
            FROM trades t
            GROUP BY 1, 2
        ) t_agg
        FULL OUTER JOIN (
            SELECT
                date_trunc('day', tg.closed_at AT TIME ZONE 'UTC')::date AS date,
                tg.account_id,
                COUNT(*) FILTER (WHERE tg.realized_pnl > 0) AS win_count,
                COUNT(*) FILTER (WHERE tg.realized_pnl <= 0) AS loss_count
            FROM trade_groups tg
            WHERE tg.status = 'closed'
            GROUP BY 1, 2
        ) g_agg ON t_agg.date = g_agg.date AND t_agg.account_id = g_agg.account_id;
    """)

    op.execute(
        "CREATE UNIQUE INDEX ON daily_summaries (date, account_id);"
    )


def downgrade() -> None:
    # Rebuild view without multiplier
    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_summaries;")

    op.execute("""
        CREATE MATERIALIZED VIEW daily_summaries AS
        SELECT
            COALESCE(t_agg.date, g_agg.date) AS date,
            COALESCE(t_agg.account_id, g_agg.account_id) AS account_id,
            COALESCE(t_agg.gross_pnl, 0) AS gross_pnl,
            COALESCE(t_agg.net_pnl, 0) AS net_pnl,
            COALESCE(t_agg.commissions, 0) AS commissions,
            COALESCE(t_agg.trade_count, 0) AS trade_count,
            COALESCE(g_agg.win_count, 0) AS win_count,
            COALESCE(g_agg.loss_count, 0) AS loss_count
        FROM (
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
                COUNT(*) AS trade_count
            FROM trades t
            GROUP BY 1, 2
        ) t_agg
        FULL OUTER JOIN (
            SELECT
                date_trunc('day', tg.closed_at AT TIME ZONE 'UTC')::date AS date,
                tg.account_id,
                COUNT(*) FILTER (WHERE tg.realized_pnl > 0) AS win_count,
                COUNT(*) FILTER (WHERE tg.realized_pnl <= 0) AS loss_count
            FROM trade_groups tg
            WHERE tg.status = 'closed'
            GROUP BY 1, 2
        ) g_agg ON t_agg.date = g_agg.date AND t_agg.account_id = g_agg.account_id;
    """)

    op.execute(
        "CREATE UNIQUE INDEX ON daily_summaries (date, account_id);"
    )

    # Remove multiplier column
    op.drop_column("trades", "multiplier")
